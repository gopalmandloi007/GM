from setuptools import setup, find_packages

setup(
    name="trading_engine",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "pandas",
        "requests",
        "streamlit",
    ],
)
