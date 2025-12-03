# Fruit Jam Library
Browse and install community CircuitPython applications on the Adafruit Fruit Jam.

## Building
Ensure that you have python 3.x installed system-wide and all the prerequisite libraries installed using the following command:

``` shell
pip install circup requests
```

Download all CircuitPython libraries and package the application using the following command:

``` shell
python build/build.py
```

The project bundle should be found within `./dist` as a `.zip` file with the same name as your repository.
