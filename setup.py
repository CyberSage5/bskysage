from setuptools import setup, find_packages

setup(
    name="bskysage",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "atproto==0.0.60",
        "python-dotenv==1.0.0",
        "redis==5.0.1",
        "rq==1.15.1",
        "openai==1.12.0",
        "pydantic>=2.7.0",
        "loguru==0.7.2",
        "ratelimit==2.2.1",
    ],
    entry_points={
        'console_scripts': [
            'bskysage-worker=bskysage.worker:main',
            'bskysage-service=bskysage.service:main',
        ],
    },
    python_requires=">=3.8",
) 