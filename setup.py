from setuptools import setup

setup(
    name="PropertyPriceApp",
    version="1.0",
    packages=["propertypriceapp"],
    install_requires=[
        "kivy",
        "httpx",
        "jmespath",
        "parsel",
        "matplotlib",
    ],
)
