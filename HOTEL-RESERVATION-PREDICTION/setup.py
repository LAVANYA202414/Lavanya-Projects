from setuptools import setup , find_packages

# Read Requirements files line by line 
with open("requirements.txt") as f:
    requirements = f.read().splitlines()


setup(
    name= "Hotel_reservation_prediction_MLFLOW",
    version="0.1",
    author='Mandeep',
    packages=find_packages(),
    install_requires = requirements,
)


# To run setup file use :

# pip install -e .