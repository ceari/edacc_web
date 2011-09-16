from setuptools import setup

setup(
    name="edacc_web",
    version="1.0",
    author="Daniel Diepold",
    long_description="EDACC Web Frontend",
    packages=["edacc", "edacc.views", "edacc.plugins"],
    include_package_data=True,
    platforms="any",
    zip_safe=False,
    install_requires=[
        "Flask==0.6",
        "SQLAlchemy>=0.6.5",
        "rpy2>=2.1",
        "mysql-python>=1.2",
        "Flask-WTF>=0.5.2",
        "Flask-Actions>=0.5.2",
        "Flask-Cache==0.3.3",
        "PyLZMA>=0.4.2",
        "PIL>=1.1.7",
        "scipy>=0.9.0",
        "scikits.learn==0.8.1",
        "numpy>=1.5.1",
        "lxml>=2.3",
    ]
)
