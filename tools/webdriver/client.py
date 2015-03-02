import httplib
import json
import urlparse

Missing = object()

class WebDriver(object):
    session = None

    def __init__(self, config):
        #TODO: this is temporary
        self.config = config
        self.host = config["webdriver"]["host"]
        self.port = config["webdriver"]["port"]
        self.path_prefix = config["webdriver"]["path_prefix"]
        self._connection = None
        print self.config

    def connect(self):
        self._connection = httplib.HTTPConnection(self.host, self.port)

    def close_connection(self):
        if self._connection:
            self._connection.close()
        self._connection = None

    def url(self, suffix):
        return urlparse.urljoin(self.config["webdriver"]["path_prefix"], suffix)

    def send(self, method, url, body=Missing, headers=Missing):
        if not self._connection:
            self.connect()

        if isinstance(body, dict):
            body = json.dumps(body)

        if isinstance(body, unicode):
            body = body.encode("utf-8")

        if body is Missing:
            body = ""

        if headers is Missing:
            headers = {}

        self._connection.request(method, url, body, headers)

        resp = self._connection.getresponse()

        rv = Response(resp.status, resp.reason, resp.getheaders(), resp.read())

        if not rv.error:
            if url.endswith("/session") and method == "POST" and "sessionId" in rv.data:
                WebDriver.session = Session(self, rv.data["sessionId"])
            elif url.endswith("/session/%s" % self.session.session_id) and method == "DELETE":
                WebDriver.session = None
                self.close_connection()

        return rv

    def new_session(self, session_id=Missing, required_capabilities=Missing,
                    desired_capabilites=Missing, raw_body=Missing, headers=Missing):
        if raw_body is not Missing:
            body = raw_body
        else:
            body = {"capabilities": {"desiredCapabilites":{}}}
            if session_id is not Missing:
                body["sessionId"] = session_id
            if desired_capabilites is not Missing:
                body["desired_capabilites"] = desired_capabilites
            if required_capabilities is not Missing:
                body["required_capabilities"] = required_capabilities

        rv = self.send("POST", self.url("session"), body, headers)
        return rv

    def end_session(self, session_id, raw_body=Missing, headers=Missing):
        url = self.url("session/%s" % session_id)
        return self.send("DELETE", url, raw_body, headers)

class Session(object):
    def __init__(self, client, session_id=None):
        self.session_id = session_id
        self.client = client

    def start(self, **kwargs):
        resp = self.client.new_session(**kwargs)
        if not resp.error:
            self.session_id = resp.data["sessionId"]
        return resp

    def end(self, **kwargs):
        if self.session_id:
            resp = self.client.end_session(self.session_id, **kwargs)
            if not resp.error:
                self.session_id = None
            return resp

    def __enter__(self):
        resp = self.start()
        if resp.error:
            raise Exception(resp)
        return self

    def __exit__(self, *args, **kwargs):
        resp = self.end()
        if resp.error:
            raise Exception(resp)

    def url(self, path, scheme="http", subdomain=None, alt_port=False):
        if subdomain is not None:
            host = self.client.config["server"]["domains"][subdomain]
        else:
            host = self.client.config["server"]["host"]

        if alt_port:
            if scheme != "http":
                raise ValueError("Only http supports multiple ports")
            port_index = 1
        else:
            port_index = 0
        port = self.client.config["server"]["ports"][scheme][port_index]

        netloc = "%s:%s" % (host, port)

        return urlparse.urlunsplit((scheme, netloc, path, "", ""))

    def send_command(self, method, url, body=Missing, headers=Missing):
        url = self.client.url(urlparse.urljoin("session/%s/" % self.session_id, url))
        return self.client.send(method, url, body, headers)

    def get(self, url, raw_body=Missing, headers=Missing):
        if raw_body is not Missing:
            body = raw_body
        else:
            if urlparse.urlsplit(url).netloc is None:
                return self.url(url)
            body = {"url": url}
        return self.send_command("POST", "url", body, headers)

    def get_current_url(self, raw_body=Missing, headers=Missing):
        return self.send_command("GET", "url", raw_body, headers)

    def go_back(self, raw_body=Missing, headers=Missing):
        return self.send_command("POST", "back", raw_body, headers)

    def go_forward(self, raw_body=Missing, headers=Missing):
        return self.send_command("POST", "forward", raw_body, headers)

    def refresh(self, raw_body=Missing, headers=Missing):
        return self.send_command("POST", "refresh", raw_body, headers)

    def get_title(self, raw_body=Missing, headers=Missing):
        return self.send_command("GET", "title", raw_body, headers)

    def get_window_handle(self, raw_body=Missing, headers=Missing):
        return self.send_command("GET", "window_handle", raw_body, headers)

    def get_window_handles(self, raw_body=Missing, headers=Missing):
        return self.send_command("GET", "window_handles", raw_body, headers)

    def close(self, raw_body=Missing, headers=Missing):
        return self.send_command("DELETE", "window_handle", raw_body, headers)

    def set_window_size(self, height, width, raw_body=Missing, headers=Missing):
        if self.raw_body is Missing:
            body = {"width": width,
                    "height": height}
        else:
            body = raw_body
        return self.send_command("POST", "window/size", body, headers)

    def get_window_size(self, raw_body=Missing, headers=Missing):
        return self.send_command("GET", "window/size", raw_body, headers)

    def maximize_window(self, raw_body=Missing, headers=Missing):
        return self.send_command("POST", "window/maximize", raw_body, headers)

    # TODO: not properly defined
    # def fullscreen_window(self, raw_body=Missing, headers=Missing):
    #     return self.send_command("POST", "", raw_body, headers)

    #[...]

    def find_element(self, strategy, selector, raw_body=Missing, headers=Missing):
        if raw_body is Missing:
            body = {"using": strategy,
                    "value": selector}
        else:
            body = raw_body
        resp = self.send_command("POST", "element", body, headers)
        try:
            elem = self.element(resp.data["value"])
        except Exception as e:
            elem = None
        return resp, elem

    def element(self, data):
        return Element(self, data["element-6066-11e4-a52e-4f735466cecf"])


    #[...]

    def execute_script(self, script, args=Missing, raw_body=Missing, headers=Missing):
        if args is Missing:
            args = []

        if raw_body is Missing:
            body = {
                "script": script,
                "args": args
            }
        else:
            body = raw_body
        return self.send_command("POST", "execute", body, headers)

class Element(object):
    def __init__(self, session, id):
        self.session = session
        self.id = id

    def url(self, suffix):
        return "element/%s/%s" % (self.id, suffix)

    def find_element(self, strategy, selector, raw_body=Missing, headers=Missing):
        if raw_body is Missing:
            body = {"using": strategy,
                    "value": selector}
        else:
            body = raw_body

        resp = self.session.send_command("POST", self.url("element"), body, headers)
        try:
            elem = self.session.element(resp.data["value"])
        except Exception:
            elem = None
        return resp, elem

    def send_keys(self, keys, raw_body=Missing, headers=Missing):
        if isinstance(keys, (str, unicode)):
            keys = [char for char in keys]
        if raw_body is Missing:
            body = {"value": keys}
        else:
            body = raw_body
        return self.session.send_command("POST", self.url("value"), body, headers)

class Response(object):
    def __init__(self, status, reason, headers, body):
        self.status = status
        self.reason = reason
        self.headers = headers
        self.raw_body = body

        if body:
            self.data = json.loads(body)
        else:
            self.data = None

        self.error = status != 200


    def __repr__(self):
        return "<Response %s %s>" % (self.status, self.raw_body)