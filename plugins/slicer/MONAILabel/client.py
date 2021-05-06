import cgi
import http.client
import json
import logging
import mimetypes
import os
import tempfile
from urllib.parse import quote_plus
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class MONAILabelClient:
    def __init__(self, server_url, tmpdir=None):
        self._server_url = server_url
        self.tmpdir = tmpdir if tmpdir else tempfile.tempdir

    def get_server_url(self):
        return self._server_url

    def set_server_url(self, server_url):
        self._server_url = server_url

    def info(self):
        selector = '/info/'
        status, response, _ = MONAILabelUtils.http_method('GET', self._server_url, selector)
        if status != 200:
            raise MONAILabelException(MONAILabelError.SERVER_ERROR, 'Status: {}; Response: {}'.format(status, response))

        response = response.decode('utf-8') if isinstance(response, bytes) else response
        logging.debug('Response: {}'.format(response))
        return json.loads(response)

    def next_sample(self, params):
        selector = '/activelearning/sample'
        status, response, _ = MONAILabelUtils.http_method('POST', self._server_url, selector, params)
        if status != 200:
            raise MONAILabelException(MONAILabelError.SERVER_ERROR, 'Status: {}; Response: {}'.format(status, response))

        response = response.decode('utf-8') if isinstance(response, bytes) else response
        logging.debug('Response: {}'.format(response))
        return json.loads(response)

    def save_label(self, image_in, label_in):
        selector = '/activelearning/label?image={}'.format(
            MONAILabelUtils.urllib_quote_plus(image_in))
        fields = {}
        files = {'label': label_in}

        status, response, _ = MONAILabelUtils.http_multipart('PUT', self._server_url, selector, fields, files)
        if status != 200:
            raise MONAILabelException(MONAILabelError.SERVER_ERROR, 'Status: {}; Response: {}'.format(status, response))

        response = response.decode('utf-8') if isinstance(response, bytes) else response
        logging.debug('Response: {}'.format(response))
        return json.loads(response)

    # def postproc_label(self, method, image_in, label_in):
    #     selector = '/postproc/{}?image={}'.format(
    #         MONAILabelUtils.urllib_quote_plus(method),
    #         MONAILabelUtils.urllib_quote_plus(image_in))

    #     status, form, files = MONAILabelUtils.http_method('POST', self._server_url, selector, params)
    #     if status != 200:
    #         raise MONAILabelException(MONAILabelError.SERVER_ERROR, 'Status: {}; Response: {}'.format(status, form))

    #     form = json.loads(form) if isinstance(form, str) else form
    #     params = form.get('params') if files else form
    #     params = json.loads(params) if isinstance(params, str) else params

    #     image_out = MONAILabelUtils.save_result(files, self.tmpdir)
    #     return image_out, params

    def postproc_label(self, method, image_in, label_in):
        selector = '/postproc/scrib?method={}&image={}'.format(
            MONAILabelUtils.urllib_quote_plus(method),
            MONAILabelUtils.urllib_quote_plus(image_in))
        fields = {}
        files = {'label': label_in}

        status, response, _ = MONAILabelUtils.http_multipart('POST', self._server_url, selector, fields, files)
        if status != 200:
            raise MONAILabelException(MONAILabelError.SERVER_ERROR, 'Status: {}; Response: {}'.format(status, response))

        response = response.decode('utf-8') if isinstance(response, bytes) else response
        logging.debug('Response: {}'.format(response))
        return json.loads(response)

    def inference(self, model, image_in, params):
        selector = '/inference/{}?image={}'.format(
            MONAILabelUtils.urllib_quote_plus(model),
            MONAILabelUtils.urllib_quote_plus(image_in))

        status, form, files = MONAILabelUtils.http_method('POST', self._server_url, selector, params)
        if status != 200:
            raise MONAILabelException(MONAILabelError.SERVER_ERROR, 'Status: {}; Response: {}'.format(status, form))

        form = json.loads(form) if isinstance(form, str) else form
        params = form.get('params') if files else form
        params = json.loads(params) if isinstance(params, str) else params

        image_out = MONAILabelUtils.save_result(files, self.tmpdir)
        return image_out, params

    def train_start(self, params):
        selector = '/train/'
        status, response, _ = MONAILabelUtils.http_method('POST', self._server_url, selector, params)
        if status != 200:
            raise MONAILabelException(MONAILabelError.SERVER_ERROR, 'Status: {}; Response: {}'.format(status, response))

        response = response.decode('utf-8') if isinstance(response, bytes) else response
        logging.debug('Response: {}'.format(response))
        return json.loads(response)

    def train_stop(self):
        selector = '/train/'
        status, response, _ = MONAILabelUtils.http_method('DELETE', self._server_url, selector)
        if status != 200:
            raise MONAILabelException(MONAILabelError.SERVER_ERROR, 'Status: {}; Response: {}'.format(status, response))

        response = response.decode('utf-8') if isinstance(response, bytes) else response
        logging.debug('Response: {}'.format(response))
        return json.loads(response)

    def train_status(self, check_if_running=False):
        selector = '/train/'
        if check_if_running:
            selector += '?check_if_running=true'
        status, response, _ = MONAILabelUtils.http_method('GET', self._server_url, selector)
        if check_if_running:
            return status == 200

        if status != 200:
            raise MONAILabelException(MONAILabelError.SERVER_ERROR, 'Status: {}; Response: {}'.format(status, response))

        response = response.decode('utf-8') if isinstance(response, bytes) else response
        logging.debug('Response: {}'.format(response))
        return json.loads(response)


class MONAILabelError:
    RESULT_NOT_FOUND = 1
    SERVER_ERROR = 2
    UNKNOWN = 3


class MONAILabelException(Exception):
    def __init__(self, error, msg):
        self.error = error
        self.msg = msg


class MONAILabelUtils:
    @staticmethod
    def http_method(method, server_url, selector, body=None):
        logging.debug('{} {}{}'.format(method, server_url, selector))

        parsed = urlparse(server_url)
        path = parsed.path.rstrip('/')
        selector = path + '/' + selector.lstrip('/')
        logging.debug('URI Path: {}'.format(selector))

        conn = http.client.HTTPConnection(parsed.hostname, parsed.port)
        print()
        print('http_method')
        print(method)
        print(selector)
        print(body)
        print()
        conn.request(method, selector, body=json.dumps(body) if body else None)
        return MONAILabelUtils.send_response(conn)

    @staticmethod
    def http_multipart(method, server_url, selector, fields, files):
        logging.debug('{} {}{}'.format(method, server_url, selector))

        content_type, body = MONAILabelUtils.encode_multipart_formdata(fields, files)
        headers = {'content-type': content_type, 'content-length': str(len(body))}

        parsed = urlparse(server_url)
        path = parsed.path.rstrip('/')
        selector = path + '/' + selector.lstrip('/')
        logging.debug('URI Path: {}'.format(selector))

        conn = http.client.HTTPConnection(parsed.hostname, parsed.port)
        print()
        print('http_multipart')
        print(method)
        print(selector)
        print(body)
        print(headers)
        print()
        conn.request(method, selector, body, headers)
        return MONAILabelUtils.send_response(conn, content_type)

    @staticmethod
    def send_response(conn, content_type="application/json"):
        response = conn.getresponse()
        logging.debug('HTTP Response Code: {}'.format(response.status))
        logging.debug('HTTP Response Message: {}'.format(response.reason))
        logging.debug('HTTP Response Headers: {}'.format(response.getheaders()))

        response_content_type = response.getheader('content-type', content_type)
        logging.debug('HTTP Response Content-Type: {}'.format(response_content_type))

        if 'multipart' in response_content_type:
            if response.status == 200:
                form, files = MONAILabelUtils.parse_multipart(response.fp if response.fp else response, response.msg)
                logging.debug('Response FORM: {}'.format(form))
                logging.debug('Response FILES: {}'.format(files.keys()))
                return response.status, form, files
            else:
                return response.status, response.read(), None

        logging.debug('Reading status/content from simple response!')
        return response.status, response.read(), None

    @staticmethod
    def save_result(files, tmpdir):
        for name in files:
            data = files[name]
            result_file = os.path.join(tmpdir, name)

            logging.debug('Saving {} to {}; Size: {}'.format(name, result_file, len(data)))
            dir_path = os.path.dirname(os.path.realpath(result_file))
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)

            with open(result_file, "wb") as f:
                if isinstance(data, bytes):
                    f.write(data)
                else:
                    f.write(data.encode('utf-8'))

            # Currently only one file per response supported
            return result_file

    @staticmethod
    def encode_multipart_formdata(fields, files):
        limit = '----------lImIt_of_THE_fIle_eW_$'
        lines = []
        for (key, value) in fields.items():
            lines.append('--' + limit)
            lines.append('Content-Disposition: form-data; name="%s"' % key)
            lines.append('')
            lines.append(value)
        for (key, filename) in files.items():
            lines.append('--' + limit)
            lines.append('Content-Disposition: form-data; name="%s"; filename="%s"' % (key, filename))
            lines.append('Content-Type: %s' % MONAILabelUtils.get_content_type(filename))
            lines.append('')
            with open(filename, mode='rb') as f:
                data = f.read()
                lines.append(data)
        lines.append('--' + limit + '--')
        lines.append('')

        body = bytearray()
        for line in lines:
            body.extend(line if isinstance(line, bytes) else line.encode('utf-8'))
            body.extend(b'\r\n')

        content_type = 'multipart/form-data; boundary=%s' % limit
        return content_type, body

    @staticmethod
    def get_content_type(filename):
        return mimetypes.guess_type(filename)[0] or 'application/octet-stream'

    @staticmethod
    def parse_multipart(fp, headers):
        fs = cgi.FieldStorage(
            fp=fp,
            environ={'REQUEST_METHOD': 'POST'},
            headers=headers,
            keep_blank_values=True
        )
        form = {}
        files = {}
        if hasattr(fs, 'list') and isinstance(fs.list, list):
            for f in fs.list:
                logger.debug('FILE-NAME: {}; NAME: {}; SIZE: {}'.format(f.filename, f.name, len(f.value)))
                if f.filename:
                    files[f.filename] = f.value
                else:
                    form[f.name] = f.value
        return form, files

    @staticmethod
    def urllib_quote_plus(s):
        return quote_plus(s)
