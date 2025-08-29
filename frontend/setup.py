from setuptools import setup, find_packages

setup(
    name="trading_engine",
    version="0.1.0",
    description="Definedge Trading Engine - API wrapper and utilities",
    author="Gopal Mandloi",
    packages=find_packages(),
    install_requires=[
        "requests",
        "pyotp",
        "streamlit"
    ],
    python_requires=">=3.8",
)
