import os
import argparse
import sys
import re
import multiprocessing as mp

HOME_PATH = os.path.expandvars('$HOME') + "/work"

class ProcessMDFileDriver(object):
    def __init__(self, args):
        self.md_file_list = []
        self.branch_name = args.branch_name
        self.run_number = args.run_number
        self.remote = args.remote
        self.refs = args.refs

    def find_md_file(self, md_file_path):
        md_file_list = []
        try:
            for file in os.listdir(md_file_path):
                if os.path.isfile(os.path.join(md_file_path, file)):
                    if file.endswith('.md'):
                        self.md_file_list.append(os.path.join(md_file_path, file))
                else:
                    self.find_md_file(os.path.join(md_file_path, file))
        except OSError:
            print("[ERROR] %s does not exist" % md_file_path)

    def get_md_list(self):
        return self.md_file_list

    def process_md_file(self, md_file):
        md_file = "/gluon-nlp/" + re.search(r"[d][o][c][s][/][e][x][a][m][p][l][e](.*)", md_file).group(0)
        dir_name = HOME_PATH + "/gluon-nlp"
        base_name = md_file[0:-3]
        ipynb_file = base_name + ".ipynb"
        log_file = base_name + ".stdout.log"
        batch_exit_code = os.system("python3 %s/tools/batch/submit-job.py --region us-east-1 --wait \
                  --timeout 3600 --saved-output %s/docs/examples \
                  --name GluonNLP-%s-%s \
                  --save-path batch/%s/%s/gluon-nlp/docs/examples \
                  --work-dir . --source-ref %s \
                  --remote https://github.com/%s \
                  --command 'python3 -m pip install --quiet nbformat notedown jupyter_client ipykernel && python3 /gluon-nlp/docs/md2ipynb.py %s | tee > %s'" % \
                  (dir_name, dir_name, self.branch_name, self.run_number, self.branch_name, \
                    self.run_number, self.refs, self.remote, md_file, log_file))

        os.system("aws s3api wait object-exists --bucket gluon-nlp-dev \
                  --key batch/%s/%s%s" % \
                  (self.branch_name, self.run_number, log_file))
        os.system("aws s3 cp s3://gluon-nlp-dev/batch/%s/%s%s %s" % \
                  (self.branch_name, self.run_number, log_file, HOME_PATH + log_file))
        os.system("cat %s" % log_file)

        if batch_exit_code != 0:
            print("AWS Batch Task Failed")
        else:
            os.system("aws s3api wait object-exists --bucket gluon-nlp-dev \
                  --key batch/%s/%s%s" % \
                  (self.branch_name, self.run_number, ipynb_file))
            os.system("aws s3 cp s3://gluon-nlp-dev/batch/%s/%s%s %s" % \
                  (self.branch_name, self.run_number, ipynb_file, HOME_PATH + ipynb_file))
        sys.exit(batch_exit_code)

    def upload_website(self):
        os.chdir(HOME_PATH + "/gluon-nlp")
        os.system("make docs_local")
        os.system("aws s3 sync --delete docs/_build/html/ s3://gluon-nlp-dev/%s/ --acl public-read" % \
                  self.branch_name)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--branch-name', help='branch name of the repo.', type=str, default='master')
    parser.add_argument('--run-number', help='number of worflow run', type=str, default=None)
    parser.add_argument('--remote', help='git repo address.', type=str, default='https://github.com/dmlc/gluon-nlp')
    parser.add_argument('--refs', help='ref in the repo.', type=str, default='master')
    args = parser.parse_args()

    driver = ProcessMDFileDriver(args)
    driver.find_md_file(HOME_PATH + '/gluon-nlp/docs/examples')

    # pool = mp.Pool(processes=4)
    # pool.map(driver.process_md_file, driver.get_md_list())

    for f in driver.get_md_list():
        driver.process_md_file(f)
