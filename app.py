# -*- coding: utf8 -*-
#
# Copyright (C) 2015 Daniel Lombraña González
#
# Deployments is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Deployments is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Deployments.  If not, see <http://www.gnu.org/licenses/>.
from flask import Flask, request, abort
import subprocess
import config
import hmac
import hashlib
app = Flask(__name__)

@app.route("/", methods=['GET', 'POST'])
def event_handler():
    """Handle deployment webhooks from Github."""
    signature = request.headers.get('X-GITHUB-SIGNATURE')
    sha_name, signature = request.headers.get('X-Hub-Signature').split('=')
    mac = hmac.new(config.SECRET, msg=request.data, digestmod=hashlib.sha1)
    if sha_name == 'sha1' and compare_digest(mac.hexdigest(), bytes(signature)):
        if request.method == 'POST':
            if request.headers.get('X-GITHUB-EVENT') == 'pull_request':
                if request.json['action'] == 'closed' and request.json['pull_request']['merged'] is True:
                    print start_deployment(request.json['pull_request'])
                    return "Pull request merged!"
                return "Pull Request created!"
            if request.headers.get('X-GITHUB-EVENT') == 'deployment':
                print request.json
                return request.json
        else:
            return "Hello!"
    else:
        return abort(403)


def start_deployment(pull_request):
    """Start a deployment."""
    print "Creating deployment"
    for repo in config.REPOS:
        if repo['repo'] == pull_request['head']['repo']['full_name']:
            subprocess.Popen(['git', "fetch"], cwd=repo['folder'])
            subprocess.Popen(['git', 'pull',  'origin', 'master'], cwd=repo['folder'])
            return "Deployment done!"
    return "Deployment canceled."

# See http://stackoverflow.com/questions/18168819/how-to-securely-verify-an-hmac-in-python-2-7
def compare_digest(x, y):
    """Compare to hmac digests."""
    if not (isinstance(x, bytes) and isinstance(y, bytes)):
        raise TypeError("both inputs should be instances of bytes")
    if len(x) != len(y):
        return False
    result = 0
    result = sum(a != b for a, b in zip(x, y))
    return result == 0


if __name__ == "__main__":
    app.debug = config.DEBUG
    app.run()
