# PyIVLE - A Python IVLE API Wrapper

PyIVLE is a Python package that provides access to the [NUS IVLE LAPI](https://wiki.nus.edu.sg/display/ivlelapi/IVLE+LAPI+Overview). 

PyIVLE implements all API methods, but is not 100% tested. If you encounter a problem, please submit an issue!

## Installation

Include the `pyivle` folder with your application.

```
git clone https://github.com/wryyl/pyivle.git
```

## Usage

```python
import pyivle

# Authenticate
p = pyivle.Pyivle(API_KEY)
p.login(USER_ID, PASSWORD)

# Get your name and user ID
me = p.profile_view()
print me.Results[0].Name, me.Results[0].UserID

# List enrolled modules by course code
modules = p.modules()
for mod in modules.Results:
    print mod.CourseCode

# Downloading a file
response = p.download_file(fileId)
with open(fileName, 'wb') as f:
    f.write(response.read())
```

By default, PyIVLE transforms JSON objects into namedtuples for convenience. If you wish to have JSON objects represented as dicts instead:

```python
p.use_namedtuple(False)

# Get your name and user ID
me = p.profile_view()
print me.Results[0]['Name'], me.Results[0]['UserID']
```

## API Key

You will need to get an API key here: https://ivle.nus.edu.sg/LAPI/default.aspx

## License

This project is licensed under the terms of the MIT license.
