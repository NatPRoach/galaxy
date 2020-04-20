import os
from collections import namedtuple
from datetime import timedelta

import pytest

from galaxy import config
from galaxy.util import listify

TestData = namedtuple('TestData', ('key', 'expected', 'loaded'))

# TODO: all these will be fixed
DO_NOT_TEST = [
    'database_connection',
    'pretty_datetime_format',
    'heartbeat_log',
    'ftp_upload_dir_template',
    'workflow_resource_params_mapper',
    'user_tool_filters',
    'user_tool_label_filters',
    'amqp_internal_connection',
]


class ExpectedValues:

    RESOLVERS = {
        'disable_library_comptypes': [''],  # TODO: we can do better
        'mulled_channels': listify,
        'object_store_store_by': 'uuid',
        'password_expiration_period': timedelta,
        'persistent_communication_rooms': listify,
        'statsd_host': '',  # TODO: do we need '' as the default?
        'tool_config_file': listify,
        'tool_data_table_config_path': listify,
        'tool_filters': listify,
        'tool_label_filters': listify,
        'tool_section_filters': listify,
        'toolbox_filter_base_modules': listify,
        'use_remote_user': None,  # TODO: should be False (config logic incorrect)
        'user_library_import_symlink_whitelist': listify,
        'user_tool_section_filters': listify,
    }
    # RESOLVERS provides expected values for config options.
    # - key: config option
    # - value: expected value or a callable. The callable will be called with a
    #   single argument, which is the default value of the config option.

    def __init__(self, config):
        self._config = config
        self._load_paths()

    def _load_paths(self):
        self._expected_paths = {
            'admin_tool_recommendations_path': self._in_config_dir('tool_recommendations_overwrite.yml'),
            'auth_config_file': self._in_config_dir('auth_conf.xml'),
            'build_sites_config_file': self._in_sample_dir('build_sites.yml.sample'),
            'builds_file_path': self._in_root_dir('tool-data/shared/ucsc/builds.txt'),
            'citation_cache_data_dir': self._in_data_dir('citations/data'),
            'citation_cache_lock_dir': self._in_data_dir('citations/locks'),
            'cluster_files_directory': self._in_data_dir('pbs'),
            'config_dir': self._in_config_dir(),
            'data_dir': self._in_data_dir(),
            'data_manager_config_file': self._in_config_dir('data_manager_conf.xml'),
            'datatypes_config_file': self._in_sample_dir('datatypes_conf.xml.sample'),
            'dependency_resolvers_config_file': self._in_config_dir('dependency_resolvers_conf.xml'),
            'dynamic_proxy_session_map': self._in_data_dir('session_map.sqlite'),
            'file_path': self._in_data_dir('objects'),
            'galaxy_data_manager_data_path': self._in_root_dir('tool-data'),
            'integrated_tool_panel_config': self._in_managed_config_dir('integrated_tool_panel.xml'),
            'interactivetools_map': self._in_data_dir('interactivetools_map.sqlite'),
            'involucro_path': self._in_root_dir('involucro'),
            'job_config_file': self._in_config_dir('job_conf.xml'),
            'job_metrics_config_file': self._in_sample_dir('job_metrics_conf.xml.sample'),
            'job_resource_params_file': self._in_config_dir('job_resource_params_conf.xml'),
            'len_file_path': self._in_root_dir('tool-data/shared/ucsc/chrom'),
            'managed_config_dir': self._in_managed_config_dir(),
            'markdown_export_css': self._in_config_dir('markdown_export.css'),
            'markdown_export_css_invocation_reports': self._in_config_dir('markdown_export_invocation_reports.css'),
            'markdown_export_css_pages': self._in_config_dir('markdown_export_pages.css'),
            'migrated_tools_config': self._in_managed_config_dir('migrated_tools_conf.xml'),
            'mulled_resolution_cache_data_dir': self._in_data_dir('mulled/data'),
            'mulled_resolution_cache_lock_dir': self._in_data_dir('mulled/locks'),
            'new_file_path': self._in_data_dir('tmp'),
            'object_store_config_file': self._in_config_dir('object_store_conf.xml'),
            'oidc_backends_config_file': self._in_config_dir('oidc_backends_config.xml'),
            'oidc_config_file': self._in_config_dir('oidc_config.xml'),
            'openid_consumer_cache_path': self._in_data_dir('openid_consumer_cache'),
            'sanitize_whitelist_file': self._in_managed_config_dir('sanitize_whitelist.txt'),
            'shed_data_manager_config_file': self._in_managed_config_dir('shed_data_manager_conf.xml'),
            'shed_tool_config_file': self._in_managed_config_dir('shed_tool_conf.xml'),
            'shed_tool_data_path': self._in_root_dir('tool-data'),
            'shed_tool_data_table_config': self._in_managed_config_dir('shed_tool_data_table_conf.xml'),
            'template_cache_path': self._in_data_dir('compiled_templates'),
            'tool_config_file': self._in_sample_dir('tool_conf.xml.sample'),
            'tool_data_path': self._in_root_dir('tool-data'),
            'tool_data_table_config_path': self._in_sample_dir('tool_data_table_conf.xml.sample'),
            'tool_path': self._in_root_dir('tools'),
            'tool_sheds_config_file': self._in_config_dir('tool_sheds_conf.xml'),
            'tool_test_data_directories': self._in_root_dir('test-data'),
            'user_preferences_extra_conf_path': self._in_config_dir('user_preferences_extra_conf.yml'),
            'whitelist_file': self._in_config_dir('disposable_email_whitelist.conf'),
            'workflow_resource_params_file': self._in_config_dir('workflow_resource_params_conf.xml'),
            'workflow_schedulers_config_file': self._in_config_dir('workflow_schedulers_conf.xml'),
        }
        # _expected_paths provides expected values for config options that are paths. Each value is
        # wrapped in a function that ensures that the path (a) is resolved w.r.t. its parent as per
        # schema and/or config module; and (b) is an absolute path. The base config paths used by
        # each function are tested separately (see tests of base config properties in this module).
        # The values are hardcoded intentionally for the sake of keeping the test readable and
        # simple. They correspond to schema defaults, and should be adjusted if the schema is
        # modified.

    def _in_root_dir(self, path=None):
        return self._in_dir(self._config.root, path)

    def _in_config_dir(self, path=None):
        return self._in_dir(self._config.config_dir, path)

    def _in_data_dir(self, path=None):
        return self._in_dir(self._config.data_dir, path)

    def _in_managed_config_dir(self, path=None):
        return self._in_dir(self._config.managed_config_dir, path)

    def _in_sample_dir(self, path=None):
        return self._in_dir(self._config.sample_config_dir, path)

    def _in_dir(self, _dir, path):
        return os.path.join(_dir, path) if path else _dir

    def get_value(self, key, data):
        value = data.get('default')
        # 1. If this is a path, resolve it
        if key in self._expected_paths:
            value = self._expected_paths[key]
        # 2. AFTER resolving paths, apply resolver, if one exists
        if key in ExpectedValues.RESOLVERS:
            resolver = ExpectedValues.RESOLVERS[key]
            if callable(resolver):
                value = resolver(value)
            else:
                value = resolver
        return value


@pytest.fixture
def mock_config_file(monkeypatch):
    # Set this to return None to force the creation of base config directories
    # in _set_config_directories(). Used to test the values of these directories only.
    monkeypatch.setattr(config, 'find_config_file', lambda x: None)


@pytest.fixture
def mock_config_running_from_source(monkeypatch, mock_config_file):
    # Simulated condition: running from source, config_file is None.
    monkeypatch.setattr(config, 'running_from_source', True)


@pytest.fixture
def mock_config_running_not_from_source(monkeypatch, mock_config_file):
    # Simulated condition: running not from source, config_file is None.
    monkeypatch.setattr(config, 'running_from_source', False)


@pytest.fixture
def appconfig(monkeypatch):
    return config.Configuration()


def test_root(appconfig):
    assert appconfig.root == os.path.abspath('.')


def test_base_config_if_running_from_source(mock_config_running_from_source, appconfig):
    assert not appconfig.config_file
    assert appconfig.config_dir == os.path.join(appconfig.root, 'config')
    assert appconfig.data_dir == os.path.join(appconfig.root, 'database')
    assert appconfig.managed_config_dir == appconfig.config_dir


def test_base_config_if_running_not_from_source(mock_config_running_not_from_source, appconfig):
    assert not appconfig.config_file
    assert appconfig.config_dir == os.getcwd()
    assert appconfig.data_dir == os.path.join(appconfig.config_dir, 'data')
    assert appconfig.managed_config_dir == os.path.join(appconfig.data_dir, 'config')


def test_common_base_config(appconfig):
    assert appconfig.shed_tools_dir == os.path.join(appconfig.data_dir, 'shed_tools')
    assert appconfig.sample_config_dir == os.path.join(appconfig.root, 'lib', 'galaxy', 'config', 'sample')


def get_config_data():
    configuration = config.Configuration()
    ev = ExpectedValues(configuration)
    items = ((k, v) for k, v in configuration.schema.app_schema.items() if k not in DO_NOT_TEST)
    for key, data in items:
        expected = ev.get_value(key, data)
        loaded = getattr(configuration, key)
        test_data = TestData(key=key, expected=expected, loaded=loaded)
        yield pytest.param(test_data)


def get_key(test_data):
    return test_data.key


@pytest.mark.parametrize('test_data', get_config_data(), ids=get_key)
def test_config_defaults(test_data):
    assert test_data.expected == test_data.loaded
