import glob
import os
import shutil
import subprocess

try:
    from unittest.mock import patch
except ImportError:
    # py2
    from mock import patch


from notebook import jstest
from binstar_client.utils import dirs

import platform

IS_WIN = "Windows" in platform.system()

here = os.path.dirname(__file__)

# TODO: Needed because of the number of different streams... needs better
# interleaving
TEST_LOG = ".jupyter-jstest.log"

# global npm installs are bad, add the local node_modules to the path
os.environ["PATH"] = os.pathsep.join([
    os.environ["PATH"],
    os.path.abspath(os.path.join(here, "node_modules", ".bin"))
])


class NBAnacondaCloudTestController(jstest.JSController):
    """ Javascript test subclass that installs widget nbextension in test
        environment
    """
    def __init__(self, section, *args, **kwargs):
        extra_args = kwargs.pop('extra_args', None)
        super(NBAnacondaCloudTestController,
              self).__init__(section, *args, **kwargs)
        self.xunit = True

        test_cases = glob.glob(os.path.join(
            here, 'js', section, 'test_*.js'))
        js_test_dir = jstest.get_js_test_dir()

        includes = [
            os.path.join(js_test_dir, 'util.js')
        ] + glob.glob(os.path.join(here, 'js', '_*.js'))

        self.cmd = [
            'casperjs', 'test',
            '--includes={}'.format(",".join(includes)),
            '--engine={}'.format(self.engine)
        ] + test_cases

        if extra_args is not None:
            self.cmd = self.cmd + extra_args

        if IS_WIN:
            self.cmd[0] = "{}.cmd".format(self.cmd[0])

    def use_token(self):
        return os.environ.get("USE_ANACONDA_TOKEN", None)

    def add_xunit(self):
        """ Hack the setup in the middle (after paths, before server)
        """
        super(NBAnacondaCloudTestController, self).add_xunit()

        prefix = ["--sys-prefix"]
        pkg = ["--py", "nb_anacondacloud"]

        with patch.dict(os.environ, self.env.copy()):
            install_results = [
                subprocess.Popen(["jupyter"] + cmd + prefix + pkg,
                                 env=os.environ
                                 ).communicate()
                for cmd in [
                    ["serverextension", "enable"],
                    ["nbextension", "install"],
                    ["nbextension", "enable"]
                ]]

            if any(sum(install_results, tuple())):
                raise Exception(install_results)

            if (self.section == "auth") and self.use_token():
                home = os.environ["HOME"]
                _data_dir = "".join([
                    self.home.name,
                    dirs.user_data_dir[len(home):]])

                with open(TEST_LOG, "a+") as fp:
                    fp.write("\nCopying auth token to {}\n".format(
                        _data_dir
                    ))

                shutil.copytree(
                    dirs.user_data_dir,
                    _data_dir
                )

            # we patch the auth by changing the configuration... probably
            # a cleaner way to do it...
            patch_auth = False
            if (self.section == "auth") and not self.use_token():
                patch_auth = True
            nbac = "disable" if patch_auth else "enable"
            nbac_p = "enable" if patch_auth else "disable"

            with open(TEST_LOG, "a+") as fp:
                fp.write("\n\n\n-------------\n{} nbac:{} nbac_p:{}".format(
                    self.section,
                    nbac, nbac_p
                ))

            toggles = [
                [nbac, "nb_anacondacloud"],
                [nbac_p, "nb_anacondacloud.tests.patched"]]

            for toggle, ext in toggles:
                subprocess.Popen(
                    ["jupyter", "serverextension", toggle] + prefix + [ext]
                ).communicate()

            for ext_type in ["nbextension", "serverextension"]:
                subprocess.Popen(["jupyter", ext_type, "list"]).communicate()

    def launch(self, buffer_output=False, capture_output=False):
        env = os.environ.copy()
        env.update(self.env)
        if buffer_output:
            capture_output = True
        self.stdout_capturer = c = jstest.StreamCapturer(
            echo=not buffer_output)
        c.start()
        stdout = c.writefd if capture_output else None
        # stderr = subprocess.STDOUT if capture_output else None
        self.process = subprocess.Popen(
            self.cmd,
            stderr=subprocess.PIPE,
            stdout=stdout,
            env=env)

    def wait(self):
        self.process.communicate()
        self.stdout_capturer.halt()
        self.stdout = self.stdout_capturer.get_buffer()
        return self.process.returncode

    def cleanup(self):
        if hasattr(self, "stream_capturer"):
            captured = self.stream_capturer.get_buffer().decode(
                'utf-8', 'replace')
            with open(TEST_LOG, "a+") as fp:
                fp.write("-----------------------\n{} results:\n{}\n".format(
                    self.section,
                    self.server_command))
                fp.write(captured)

        super(NBAnacondaCloudTestController, self).cleanup()


def prepare_controllers(options):
    """Monkeypatched prepare_controllers for running widget js tests

    instead of notebook js tests
    """
    return (
        [
            NBAnacondaCloudTestController('auth'),
            NBAnacondaCloudTestController('noauth'),
        ],
        []
    )


def test_notebook():
    with patch.object(jstest, 'prepare_controllers', prepare_controllers):
        jstest.main()


if __name__ == '__main__':
    test_notebook()
