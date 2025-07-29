from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="mclaren-platform",
    version="1.0.0",
    author="McLaren Applied Technologies",
    author_email="platform@mclarenapplied.com",
    description="Advanced communication platform for rail connectivity and edge computing",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mclaren-applied/communication-platform",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Networking",
        "Topic :: System :: Distributed Computing",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest",
            "pytest-asyncio",
            "pytest-cov",
            "black",
            "flake8",
            "mypy",
            "pre-commit",
        ],
        "monitoring": [
            "prometheus-client",
            "grafana-api",
        ],
        "security": [
            "bandit",
            "safety",
        ],
    },
    entry_points={
        "console_scripts": [
            "mclaren-platform=mclaren_platform.main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "mclaren_platform": ["config/*.yaml"],
    },
)