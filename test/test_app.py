# -*- coding: utf8 -*-
# This file is part of deployments.
#
# Copyright (C) 2014 Daniel Lombraña González
#
# deployments is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# deployments is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with deployments. If not, see <http://www.gnu.org/licenses/>.
"""
App package for testing deployments application.

This exports:
    - Test the app

"""
import config
import json
from base import Test, PseudoRequest
from app import app, process_deployment, create_deployment, update_deployment, \
    communicate_deployment, authorize
from mock import patch, MagicMock
from nose.tools import assert_raises
from github import pull_request_opened, pull_request_closed, \
    pull_request_closed_merged, deployment, deployment_status
from subprocess import CalledProcessError


class TestApp(Test):

    """Class for Testing the deployments application."""

    def setUp(self):
        """Setup method for configuring the tests."""
        self.app = app
        self.app.config['TESTING'] = True
        self.tc = self.app.test_client()

    def test_get_403(self):
        """Test GET method returns 403 for non auth."""
        res = self.tc.get('/')
        assert res.status_code == 403, self.ERR_MSG_403_STATUS_CODE

    @patch('app.authorize', return_value=True)
    def test_get_501(self, authorize):
        """Test GET method returns 501 for auth."""
        res = self.tc.get('/')
        assert res.status_code == 501, self.ERR_MSG_501_STATUS_CODE

    def test_post_403(self):
        """Test POST method return 403 for non auth."""
        res = self.tc.post('/')
        assert res.status_code == 403, self.ERR_MSG_403_STATUS_CODE

    @patch('app.authorize', return_value=True)
    def test_post_501_missing_headers(self, authorize):
        """Test POST method with missing header returns 501 for auth."""
        res = self.tc.post('/')
        assert res.status_code == 501, self.ERR_MSG_501_STATUS_CODE

    @patch('app.authorize', return_value=True)
    def test_post_501_wrong_headers_alt(self, authorize):
        """Test POST method with wrong header returns 501 for auth."""
        self.github_headers['X-GitHub-Event'] = 'wrong'
        res = self.tc.post('/', headers=self.github_headers)
        assert res.status_code == 501, self.ERR_MSG_501_STATUS_CODE

    @patch('app.authorize', return_value=True)
    def test_post_pull_request_created(self, authorize):
        """Test POST method with pull request created event."""
        self.github_headers['X-GitHub-Event'] = 'pull_request'
        headers = self.github_headers.copy()
        headers.update(self.json_headers)
        res = self.tc.post('/', data=json.dumps(pull_request_opened),
                           headers=headers)
        assert res.status_code == 200, self.ERR_MSG_200_STATUS_CODE
        assert "Pull Request created!" in res.data, res.data

    @patch('app.authorize', return_value=True)
    def test_post_pull_request_closed(self, authorize):
        """Test POST method with pull request closed event."""
        self.github_headers['X-GitHub-Event'] = 'pull_request'
        headers = self.github_headers.copy()
        headers.update(self.json_headers)
        res = self.tc.post('/', data=json.dumps(pull_request_closed),
                           headers=headers)
        assert res.status_code == 200, self.ERR_MSG_200_STATUS_CODE
        assert "Pull Request created!" in res.data, res.data

    @patch('app.create_deployment')
    @patch('app.authorize', return_value=True)
    def test_post_pull_request_closed_merged(self, authorize,
                                             create_deployment):
        """Test POST method with pull request closed and merged event."""
        self.github_headers['X-GitHub-Event'] = 'pull_request'
        headers = self.github_headers.copy()
        headers.update(self.json_headers)
        res = self.tc.post('/', data=json.dumps(pull_request_closed_merged),
                           headers=headers)
        assert res.status_code == 200, self.ERR_MSG_200_STATUS_CODE
        assert "Pull Request merged!" in res.data, res.data
        data = pull_request_closed_merged['pull_request']
        assert create_deployment.called_with(data, config.TOKEN)

    @patch('app.process_deployment')
    @patch('app.authorize', return_value=True)
    def test_post_deployment(self, authorize, process_deployment):
        """Test POST method with deployment event."""
        self.github_headers['X-GitHub-Event'] = 'deployment'
        headers = self.github_headers.copy()
        headers.update(self.json_headers)
        res = self.tc.post('/', data=json.dumps(deployment),
                           headers=headers)
        assert res.status_code == 200, self.ERR_MSG_200_STATUS_CODE
        assert "Deployment done!" in res.data, res.data
        assert process_deployment.called_with(deployment, config.TOKEN)


    @patch('app.process_deployment', return_value=False)
    @patch('app.authorize', return_value=True)
    def test_post_deployment_fails(self, authorize, process_deployment):
        """Test POST method with deployment event fails."""
        self.github_headers['X-GitHub-Event'] = 'deployment'
        headers = self.github_headers.copy()
        headers.update(self.json_headers)
        res = self.tc.post('/', data=json.dumps(deployment),
                           headers=headers)
        assert res.status_code == 500, self.ERR_MSG_500_STATUS_CODE
        assert process_deployment.called_with(deployment, config.TOKEN)


    @patch('app.communicate_deployment')
    @patch('app.authorize', return_value=True)
    def test_post_communicate_deployment(self, authorize,
                                         communicate_deployment):
        """Test POST method with deployment_status event."""
        self.github_headers['X-GitHub-Event'] = 'deployment_status'
        headers = self.github_headers.copy()
        headers.update(self.json_headers)
        res = self.tc.post('/', data=json.dumps(deployment),
                           headers=headers)
        assert res.status_code == 200, self.ERR_MSG_200_STATUS_CODE
        assert "Update Deployment Status" in res.data, res.data
        assert communicate_deployment.called_with(deployment)

    @patch('app.update_deployment')
    @patch('app.Popen')
    def test_process_deployment(self, popen, update_deployment):
        """Test process_deployment method."""
        process_mock = MagicMock()
        attrs = {'communicate.return_value': ('ouput', 'error'),
                 'wait.return_value': 0}
        process_mock.configure_mock(**attrs)
        popen.return_value = process_mock
        res = process_deployment(deployment, config.TOKEN)
        assert res, res
        assert update_deployment.called_with(deployment, status='success')

    @patch('app.update_deployment')
    @patch('app.Popen')
    def test_process_deployment_process_error(self, popen, update_deployment):
        """Test process_deployment process_error method."""
        process_mock = MagicMock()
        attrs = {'communicate.return_value': ('ouput', 'error'),
                 'wait.return_value': 1}
        process_mock.configure_mock(**attrs)
        popen.return_value = process_mock
        res = process_deployment(deployment, config.TOKEN)
        assert res is False, res
        message = "command: %s ERROR: %s" % ('output', 'error')
        assert update_deployment.called_with(deployment, status='error',
                                             message=message)

    @patch('app.update_deployment')
    @patch('app.Popen')
    def test_process_deployment_oserror(self, popen, update_deployment):
        """Test process_deployment fails method."""
        process_mock = MagicMock()
        attrs = {'communicate.return_value': ('ouput', 'error'),
                 'wait.return_value': 1,
                 'wait.side_effect': OSError}
        process_mock.configure_mock(**attrs)
        popen.return_value = process_mock
        res = process_deployment(deployment, config.TOKEN)
        assert res is False, res
        e = OSError()
        assert update_deployment.called_with(deployment, status='error',
                                             message=str(e))

    @patch('app.requests')
    def test_create_deployment(self, requests):
        """Test create_deployment works."""
        data = pull_request_closed_merged['pull_request']
        requests.post.return_value = deployment
        res = create_deployment(data, config.TOKEN)
        assert res == deployment, res

    @patch('app.requests')
    def test_update_deployment(self, requests):
        """Test create_deployment works."""
        requests.post.return_value = PseudoRequest(json.dumps(deployment),
                                                   200,
                                                   self.json_headers)
        res = update_deployment(deployment, 'success')
        assert res, res

    @patch('app.requests')
    def test_update_deployment_fails(self, requests):
        """Test create_deployment fails."""
        requests.post.return_value = PseudoRequest(json.dumps(deployment),
                                                   404,
                                                   self.json_headers)
        res = update_deployment(deployment, 'error')
        assert res is False, res

    @patch('app.requests')
    def test_communicate_deployment(self, requests):
        """Test communicate_deployment works."""
        repo = deployment_status['repository']['full_name']
        repo_url = deployment_status['repository']['url']
        status = deployment_status['deployment_status']['state']
        status_url = deployment_status['deployment']['url']
        user = deployment_status['deployment']['payload']['deploy_user']
        msg ='Repository <%s|%s> has been deployed by *%s* with <%s/statuses|%s>.' % (repo_url,
                                                                 repo,
                                                                 user,
                                                                 status_url,
                                                                 status)
        requests.post.return_value = PseudoRequest(msg, 200, '')
        res = communicate_deployment(deployment_status)
        assert msg in res, res

    @patch('app.requests')
    def test_communicate_deployment_fails(self, requests):
        """Test communicate_deployment works."""
        repo = deployment_status['repository']['full_name']
        repo_url = deployment_status['repository']['url']
        status = deployment_status['deployment_status']['state']
        status_url = deployment_status['deployment']['url']
        user = deployment_status['deployment']['payload']['deploy_user']
        msg ='Repository <%s|%s> has been deployed by *%s* with <%s/statuses|%s>.' % (repo_url,
                                                                 repo,
                                                                 user,
                                                                 status_url,
                                                                 status)
        requests.post.side_effect = AttributeError
        res = communicate_deployment(deployment_status)
        assert msg in res, res

    def test_authorize_case_1(self):
        """Test authorize without signature."""
        request = MagicMock()
        request.headers = {'Something': 'bar'}
        assert authorize(request, config) is False

    def test_authorize_case_2(self):
        """Test authorize wit signature but wrong one."""
        request = MagicMock()
        request.headers = {'X-Hub-Signature': ''}
        assert authorize(request, config) is False

    def test_authorize_case_3(self):
        """Test authorize wit signature but wrong one."""
        request = MagicMock()
        request.headers = {'X-Hub-Signature': 'sha1='}
        assert authorize(request, config) is False

    def test_authorize_case_4(self):
        """Test authorize wit signature but wrong one."""
        request = MagicMock()
        request.headers = {'X-Hub-Signature': 'md5=signature'}
        assert authorize(request, config) is False

    def test_authorize_case_5(self):
        """Test authorize with signature."""
        import hmac
        import hashlib
        request = MagicMock()
        request.data = 'foo'
        signature = 'sha1=%s' % hmac.new(config.SECRET, msg=request.data,
                                         digestmod=hashlib.sha1).hexdigest()
        request.headers = {'X-Hub-Signature': signature}
        res = authorize(request, config)
        assert res is True, res

    def test_authorize_case_6(self):
        """Test authorize with wrong signature."""
        import hmac
        import hashlib
        request = MagicMock()
        request.data = 'foo'
        signature = 'sha1=%s1' % hmac.new(config.SECRET, msg=request.data,
                                         digestmod=hashlib.sha1).hexdigest()
        request.headers = {'X-Hub-Signature': signature}
        res = authorize(request, config)
        assert res is False, res
