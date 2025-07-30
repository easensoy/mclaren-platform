import asyncio
import logging
import docker
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
from core.interfaces import IContainerOrchestrator
from core.models import WorkloadSpec, DeploymentResult, WorkloadStatus, Event
from core.events import EventBus

class ContainerManager(IContainerOrchestrator):
    
    def __init__(self, config: Dict[str, Any], event_bus: EventBus):
        self._config = config
        self._event_bus = event_bus
        self._docker_client: Optional[docker.DockerClient] = None
        self._workload_registry: Dict[str, Dict[str, Any]] = {}
        self._health_monitoring_task: Optional[asyncio.Task] = None
        self._logger = logging.getLogger(__name__)
        
        self._event_bus.subscribe('container_health_failed', self._handle_health_failure)
        self._event_bus.subscribe('ota_update_requested', self._handle_ota_update)
    
    async def initialize(self) -> None:
        try:
            self._docker_client = docker.from_env()
            self._docker_client.ping()
            
            await self._discover_existing_workloads()
            
            await self._start_health_monitoring()
            
            self._logger.info(f"Container manager initialized with {len(self._workload_registry)} existing workloads")
            
            await self._event_bus.publish(Event(
                event_type='container_manager_initialized',
                data={'existing_workloads': len(self._workload_registry)}
            ))
            
        except Exception as e:
            self._docker_client = None
            self._logger.warning(f"Docker not available, container features disabled: {e}")
            
            await self._event_bus.publish(Event(
                event_type='container_manager_initialized',
                data={'existing_workloads': 0, 'docker_available': False}
            ))
    
    async def deploy_workload(self, spec: WorkloadSpec) -> DeploymentResult:
        try:
            self._logger.info(f"Deploying workload: {spec.name}")
            
            validation_result = await self._validate_workload_spec(spec)
            if not validation_result['valid']:
                return DeploymentResult(
                    success=False,
                    workload_id="",
                    message=f"Validation failed: {validation_result['errors']}",
                    deployed_at=datetime.now()
                )
            
            container_config = await self._prepare_container_config(spec)
            
            await self._pull_arm_image(spec.image)
            
            deployed_containers = []
            for replica in range(spec.replicas):
                container_name = f"{spec.name}-{replica}"
                container_config['name'] = container_name
                
                container = self._docker_client.containers.run(**container_config)
                deployed_containers.append(container.id)
            
            workload_id = f"workload-{spec.name}-{int(datetime.now().timestamp())}"
            self._workload_registry[spec.name] = {
                'workload_id': workload_id,
                'spec': spec,
                'container_ids': deployed_containers,
                'deployed_at': datetime.now(),
                'status': 'running',
                'health_checks_passed': 0
            }
            
            await asyncio.sleep(10)
            health_status = await self.get_workload_status(spec.name)
            
            if health_status.replicas_running == spec.replicas:
                await self._event_bus.publish(Event(
                    event_type='workload_deployed_successfully',
                    data={
                        'workload_name': spec.name,
                        'workload_id': workload_id,
                        'replicas': spec.replicas
                    }
                ))
                
                return DeploymentResult(
                    success=True,
                    workload_id=workload_id,
                    message=f"Successfully deployed {spec.replicas} replicas",
                    deployed_at=datetime.now(),
                    endpoints=[f"http://localhost:{port}" for port in spec.ports]
                )
            else:
                raise Exception(f"Only {health_status.replicas_running}/{spec.replicas} replicas started successfully")
                
        except Exception as e:
            self._logger.error(f"Workload deployment failed for {spec.name}: {e}")
            
            await self._event_bus.publish(Event(
                event_type='workload_deployment_failed',
                data={'workload_name': spec.name, 'error': str(e)}
            ))
            
            return DeploymentResult(
                success=False,
                workload_id="",
                message=f"Deployment failed: {e}",
                deployed_at=datetime.now()
            )
    
    async def update_workload(self, name: str, new_spec: WorkloadSpec) -> 'UpdateResult':
        try:
            if name not in self._workload_registry:
                raise ValueError(f"Workload {name} not found")
            
            self._logger.info(f"Updating workload: {name}")
            
            current_state = self._workload_registry[name].copy()
            
            try:
                await self._perform_rolling_update(name, new_spec)
                
                health_status = await self.get_workload_status(name)
                
                if health_status.replicas_running == new_spec.replicas:
                    await self._event_bus.publish(Event(
                        event_type='workload_updated_successfully',
                        data={
                            'workload_name': name,
                            'new_image': new_spec.image,
                            'replicas': new_spec.replicas
                        }
                    ))
                    
                    return UpdateResult(
                        success=True,
                        message="Update completed successfully",
                        rollback_performed=False
                    )
                else:
                    await self._rollback_workload(name, current_state)
                    return UpdateResult(
                        success=False,
                        message="Update failed, rollback completed",
                        rollback_performed=True
                    )
                    
            except Exception as e:
                await self._rollback_workload(name, current_state)
                raise e
                
        except Exception as e:
            self._logger.error(f"Workload update failed for {name}: {e}")
            
            return UpdateResult(
                success=False,
                message=f"Update failed: {e}",
                rollback_performed=True
            )
    
    async def get_workload_status(self, name: str) -> WorkloadStatus:
        try:
            if name not in self._workload_registry:
                raise ValueError(f"Workload {name} not found")
            
            workload_info = self._workload_registry[name]
            spec = workload_info['spec']
            
            running_containers = 0
            total_cpu_usage = 0
            total_memory_usage = 0
            total_network_rx = 0
            total_network_tx = 0
            oldest_start_time = datetime.now()
            
            for container_id in workload_info['container_ids']:
                try:
                    container = self._docker_client.containers.get(container_id)
                    container.reload()
                    
                    if container.status == 'running':
                        running_containers += 1
                        
                        stats = container.stats(stream=False)
                        
                        cpu_percent = self._calculate_cpu_percent(stats)
                        total_cpu_usage += cpu_percent
                        
                        memory_usage = stats['memory_stats'].get('usage', 0) / (1024 * 1024)
                        total_memory_usage += memory_usage
                        
                        networks = stats.get('networks', {})
                        for network_stats in networks.values():
                            total_network_rx += network_stats.get('rx_bytes', 0)
                            total_network_tx += network_stats.get('tx_bytes', 0)
                        
                        started_at = datetime.fromisoformat(
                            container.attrs['State']['StartedAt'].replace('Z', '+00:00')
                        )
                        if started_at < oldest_start_time:
                            oldest_start_time = started_at
                            
                except Exception as e:
                    self._logger.warning(f"Failed to get stats for container {container_id}: {e}")
            
            uptime_seconds = (datetime.now() - oldest_start_time).total_seconds()
            
            return WorkloadStatus(
                name=name,
                status='running' if running_containers > 0 else 'stopped',
                replicas_running=running_containers,
                replicas_desired=spec.replicas,
                cpu_usage_percent=total_cpu_usage / max(running_containers, 1),
                memory_usage_mb=total_memory_usage,
                network_io={'rx_bytes': total_network_rx, 'tx_bytes': total_network_tx},
                uptime_seconds=uptime_seconds,
                last_updated=datetime.now()
            )
            
        except Exception as e:
            self._logger.error(f"Failed to get workload status for {name}: {e}")
            
            return WorkloadStatus(
                name=name,
                status='error',
                replicas_running=0,
                replicas_desired=0,
                cpu_usage_percent=0,
                memory_usage_mb=0,
                network_io={'rx_bytes': 0, 'tx_bytes': 0},
                uptime_seconds=0,
                last_updated=datetime.now()
            )
    
    async def scale_workload(self, name: str, replicas: int) -> bool:
        try:
            if name not in self._workload_registry:
                return False
            
            workload_info = self._workload_registry[name]
            current_replicas = len(workload_info['container_ids'])
            
            if replicas == current_replicas:
                return True
            
            if replicas > current_replicas:
                await self._scale_up_workload(name, replicas - current_replicas)
            else:
                await self._scale_down_workload(name, current_replicas - replicas)
            
            await self._event_bus.publish(Event(
                event_type='workload_scaled',
                data={
                    'workload_name': name,
                    'previous_replicas': current_replicas,
                    'new_replicas': replicas
                }
            ))
            
            return True
            
        except Exception as e:
            self._logger.error(f"Workload scaling failed for {name}: {e}")
            return False
    
    async def _validate_workload_spec(self, spec: WorkloadSpec) -> Dict[str, Any]:
        errors = []
        
        if not spec.name:
            errors.append("Workload name is required")
        
        if not spec.image:
            errors.append("Container image is required")
        
        if spec.replicas < 1:
            errors.append("Replicas must be at least 1")
        
        if 'memory' in spec.resources:
            if not self._validate_memory_spec(spec.resources['memory']):
                errors.append("Invalid memory specification")
        
        if 'cpu' in spec.resources:
            if not self._validate_cpu_spec(spec.resources['cpu']):
                errors.append("Invalid CPU specification")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def _validate_memory_spec(self, memory_spec: str) -> bool:
        try:
            if memory_spec.endswith(('m', 'M')):
                int(memory_spec[:-1])
                return True
            elif memory_spec.endswith(('g', 'G')):
                float(memory_spec[:-1])
                return True
            return False
        except:
            return False
    
    def _validate_cpu_spec(self, cpu_spec: str) -> bool:
        try:
            float(cpu_spec)
            return True
        except:
            return False
    
    async def _prepare_container_config(self, spec: WorkloadSpec) -> Dict[str, Any]:
        config = {
            'image': spec.image,
            'detach': True,
            'platform': 'linux/arm64',
            'restart_policy': {'Name': spec.restart_policy},
            'environment': spec.environment,
            'ports': {f"{port}/tcp": port for port in spec.ports} if spec.ports else None,
            'volumes': spec.volumes if spec.volumes else None
        }
        
        if 'memory' in spec.resources:
            config['mem_limit'] = spec.resources['memory']
        
        if 'cpu' in spec.resources:
            cpu_quota = int(float(spec.resources['cpu']) * 100000)
            config['cpu_quota'] = cpu_quota
        
        return {k: v for k, v in config.items() if v is not None}
    
    async def _pull_arm_image(self, image: str) -> None:
        try:
            self._logger.info(f"Pulling ARM64 image: {image}")
            self._docker_client.images.pull(image, platform='linux/arm64')
        except Exception as e:
            self._logger.warning(f"Failed to pull ARM64 image {image}, trying default: {e}")
            self._docker_client.images.pull(image)
    
    async def _discover_existing_workloads(self) -> None:
        try:
            containers = self._docker_client.containers.list(all=True)
            
            workload_groups = {}
            for container in containers:
                name_parts = container.name.split('-')
                if len(name_parts) >= 3:
                    workload_name = '-'.join(name_parts[:-1])
                    
                    if workload_name not in workload_groups:
                        workload_groups[workload_name] = []
                    
                    workload_groups[workload_name].append(container.id)
            
            for workload_name, container_ids in workload_groups.items():
                self._workload_registry[workload_name] = {
                    'workload_id': f"discovered-{workload_name}",
                    'spec': self._reconstruct_workload_spec(workload_name, container_ids),
                    'container_ids': container_ids,
                    'deployed_at': datetime.now(),
                    'status': 'running',
                    'health_checks_passed': 0
                }
                
        except Exception as e:
            self._logger.warning(f"Failed to discover existing workloads: {e}")
    
    def _reconstruct_workload_spec(self, workload_name: str, container_ids: List[str]) -> WorkloadSpec:
        try:
            if not container_ids:
                return WorkloadSpec(name=workload_name, image="unknown")
            
            container = self._docker_client.containers.get(container_ids[0])
            
            return WorkloadSpec(
                name=workload_name,
                image=container.image.tags[0] if container.image.tags else "unknown",
                replicas=len(container_ids),
                environment=container.attrs.get('Config', {}).get('Env', []),
                ports=[]
            )
            
        except Exception as e:
            self._logger.warning(f"Failed to reconstruct spec for {workload_name}: {e}")
            return WorkloadSpec(name=workload_name, image="unknown")
    
    def _calculate_cpu_percent(self, stats: Dict) -> float:
        try:
            cpu_delta = (stats['cpu_stats']['cpu_usage']['total_usage'] - 
                        stats['precpu_stats']['cpu_usage']['total_usage'])
            system_delta = (stats['cpu_stats']['system_cpu_usage'] - 
                           stats['precpu_stats']['system_cpu_usage'])
            
            if system_delta > 0:
                cpu_cores = len(stats['cpu_stats']['cpu_usage']['percpu_usage'])
                return (cpu_delta / system_delta) * cpu_cores * 100
            
            return 0.0
            
        except (KeyError, ZeroDivisionError, TypeError):
            return 0.0
    
    async def _start_health_monitoring(self) -> None:
        if self._health_monitoring_task:
            self._health_monitoring_task.cancel()
        
        self._health_monitoring_task = asyncio.create_task(self._health_monitoring_loop())
    
    async def _health_monitoring_loop(self) -> None:
        while True:
            try:
                interval = self._config.get('health_check_interval', 30)
                
                for workload_name in list(self._workload_registry.keys()):
                    try:
                        status = await self.get_workload_status(workload_name)
                        
                        if status.replicas_running < status.replicas_desired:
                            await self._event_bus.publish(Event(
                                event_type='workload_unhealthy',
                                data={
                                    'workload_name': workload_name,
                                    'running_replicas': status.replicas_running,
                                    'desired_replicas': status.replicas_desired
                                }
                            ))
                        
                        if status.replicas_running == status.replicas_desired:
                            self._workload_registry[workload_name]['health_checks_passed'] += 1
                        else:
                            self._workload_registry[workload_name]['health_checks_passed'] = 0
                            
                    except Exception as e:
                        self._logger.error(f"Health check failed for {workload_name}: {e}")
                
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Health monitoring loop error: {e}")
                await asyncio.sleep(30)
    
    async def _perform_rolling_update(self, name: str, new_spec: WorkloadSpec) -> None:
        workload_info = self._workload_registry[name]
        old_container_ids = workload_info['container_ids'].copy()
        
        new_config = await self._prepare_container_config(new_spec)
        
        await self._pull_arm_image(new_spec.image)
        
        new_container_ids = []
        
        try:
            for i, old_container_id in enumerate(old_container_ids):
                new_config['name'] = f"{new_spec.name}-{i}"
                new_container = self._docker_client.containers.run(**new_config)
                
                await asyncio.sleep(10)
                
                new_container.reload()
                if new_container.status == 'running':
                    new_container_ids.append(new_container.id)
                    
                    try:
                        old_container = self._docker_client.containers.get(old_container_id)
                        old_container.stop(timeout=30)
                        old_container.remove()
                    except Exception as e:
                        self._logger.warning(f"Failed to remove old container {old_container_id}: {e}")
                else:
                    raise Exception(f"New container {new_container.id} failed to start")
            
            workload_info['spec'] = new_spec
            workload_info['container_ids'] = new_container_ids
            
        except Exception as e:
            for container_id in new_container_ids:
                try:
                    container = self._docker_client.containers.get(container_id)
                    container.stop()
                    container.remove()
                except:
                    pass
            raise e
    
    async def _rollback_workload(self, name: str, previous_state: Dict[str, Any]) -> None:
        try:
            self._logger.info(f"Rolling back workload: {name}")
            
            current_info = self._workload_registry[name]
            for container_id in current_info['container_ids']:
                try:
                    container = self._docker_client.containers.get(container_id)
                    container.stop()
                    container.remove()
                except Exception as e:
                    self._logger.warning(f"Failed to stop container during rollback: {e}")
            
            self._workload_registry[name] = previous_state
            
            previous_spec = previous_state['spec']
            await self.deploy_workload(previous_spec)
            
            await self._event_bus.publish(Event(
                event_type='workload_rolled_back',
                data={'workload_name': name}
            ))
            
        except Exception as e:
            self._logger.error(f"Rollback failed for {name}: {e}")
    
    async def _scale_up_workload(self, name: str, additional_replicas: int) -> None:
        workload_info = self._workload_registry[name]
        spec = workload_info['spec']
        
        config = await self._prepare_container_config(spec)
        
        new_container_ids = []
        current_replica_count = len(workload_info['container_ids'])
        
        for i in range(additional_replicas):
            replica_index = current_replica_count + i
            config['name'] = f"{spec.name}-{replica_index}"
            
            container = self._docker_client.containers.run(**config)
            new_container_ids.append(container.id)
        
        workload_info['container_ids'].extend(new_container_ids)
        spec.replicas += additional_replicas
    
    async def _scale_down_workload(self, name: str, replicas_to_remove: int) -> None:
        workload_info = self._workload_registry[name]
        
        containers_to_remove = workload_info['container_ids'][-replicas_to_remove:]
        
        for container_id in containers_to_remove:
            try:
                container = self._docker_client.containers.get(container_id)
                container.stop(timeout=30)
                container.remove()
                workload_info['container_ids'].remove(container_id)
            except Exception as e:
                self._logger.error(f"Failed to remove container {container_id}: {e}")
        
        workload_info['spec'].replicas -= replicas_to_remove
    
    async def _handle_health_failure(self, event: Event) -> None:
        workload_name = event.data.get('workload_name')
        if workload_name in self._workload_registry:
            self._logger.warning(f"Health failure detected for workload: {workload_name}")
            
            try:
                spec = self._workload_registry[workload_name]['spec']
                await self.deploy_workload(spec)
            except Exception as e:
                self._logger.error(f"Failed to restart unhealthy workload {workload_name}: {e}")
    
    async def _handle_ota_update(self, event: Event) -> None:
        workload_name = event.data.get('workload_name')
        new_image = event.data.get('new_image')
        
        if workload_name in self._workload_registry:
            try:
                current_spec = self._workload_registry[workload_name]['spec']
                new_spec = WorkloadSpec(
                    name=current_spec.name,
                    image=new_image,
                    replicas=current_spec.replicas,
                    resources=current_spec.resources,
                    environment=current_spec.environment,
                    ports=current_spec.ports,
                    volumes=current_spec.volumes
                )
                
                await self.update_workload(workload_name, new_spec)
                
            except Exception as e:
                self._logger.error(f"OTA update failed for {workload_name}: {e}")