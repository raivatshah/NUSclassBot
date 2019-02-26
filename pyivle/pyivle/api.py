import urllib2
import urllib
import json
import re
from cookielib import CookieJar
from collections import namedtuple

apiKey = None
authToken = None
baseUrl = 'https://ivle.nus.edu.sg/api/Lapi.svc/'
downloadUrl = 'https://ivle.nus.edu.sg/api/downloadfile.ashx'

useNamedtuple = True

class InvalidAPIKeyException(Exception): pass
class InvalidLoginException(Exception): pass
class InvalidParametersException(Exception): pass
class UnauthenticatedException(Exception): pass

# call the method specified. don't add auth params by default
def call(method, params, auth=False, verb='get'):
    params = process_params(params, auth)
    if verb.lower() == 'post':
        url = baseUrl + method
        paramsEncoded = urllib.urlencode(params)
        req = urllib2.Request(url, paramsEncoded)
        jsonString = urllib2.urlopen(req).read()
    else:
        url = '%s?%s' % (baseUrl + method, urllib.urlencode(params))
        jsonString = urllib2.urlopen(url).read()

    if useNamedtuple:
        # Magic (http://stackoverflow.com/questions/6578986/how-to-convert-json-data-into-a-python-object)
        result = json.loads(jsonString, object_hook=lambda d: namedtuple('Obj', d.keys())(*d.values()))
    else:
        result = json.loads(jsonString)

    return result

# target can be either 'workbin' or 'community'
def download_file(fileid, target, auth=True):
    params = process_params({'ID': fileid, 'target': target}, auth)
    url = '%s?%s' % (downloadUrl, urllib.urlencode(params))
    res = urllib2.urlopen(url)
    return res


def get_auth_token(apiKey, userid, password):
    loginUrl = 'https://ivle.nus.edu.sg/api/login/?apikey=%s' % apiKey
    data = urllib2.urlopen(loginUrl).read()

    if len(data) == 0:
        raise InvalidAPIKeyException('API key is not valid.')

    viewstate = re.search('__VIEWSTATE.+?value="(.+?)"', data)
    if not viewstate:
        # try setting viewstate to a hardcoded value if we fail trying to parse it
        viewstate = '/wEPDwULLTEzODMyMDQxNjEPFgIeE1ZhbGlkYXRlUmVxdWVzdE1vZGUCARYCAgEPZBYEAgEPD2QWAh4Gb25ibHVyBQ91c2VySWRUb1VwcGVyKClkAgkPD2QWBB4Lb25tb3VzZW92ZXIFNWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdsb2dpbmltZzEnKS5zcmM9b2ZmaW1nLnNyYzE7Hgpvbm1vdXNlb3V0BTRkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnbG9naW5pbWcxJykuc3JjPW9uaW1nLnNyYzE7ZBgBBR5fX0NvbnRyb2xzUmVxdWlyZVBvc3RCYWNrS2V5X18WAQUJbG9naW5pbWcxYTg4Q/LO3lNCB13iJpTeINmF1JQmGv61ni1TVgDIOII='
    else:
        viewstate = viewstate.group(1)
    params = urllib.urlencode({'__VIEWSTATE': viewstate, 'userid': userid, 'password': password})

    cj = CookieJar()
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
    userToken = opener.open(loginUrl, params).read()

    if 'Login fail' in userToken or '</html>' in userToken:
        raise InvalidLoginException('Login credentials are not valid.')

    return userToken

# Adds authentication parameters to parameter list
def add_auth(params):
    if not authToken:
        raise UnauthenticatedException('Not authenticated. Login or specify auth=False (if available) if you are sure you wish to call this function without authentication.')
    params['APIKey'] = apiKey
    params['AuthToken'] = authToken
    return params

# Converts params to strings. Add auth params if specified.
def process_params(params, auth=False):
    # remove None values and convert values to Strings
    params = dict((k, str(v)) for  k, v in params.iteritems() if v)
    if auth: 
        params = add_auth(params)
    return params
