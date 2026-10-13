"""Private mock workspace setup; stub PDF validation is for browser/ledger tests only."""
import argparse,json
from pathlib import Path
from fixtures import make_workspace,assessment,stub_ready_package,authorized_preparation
import jobs

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('workspace',type=Path);ap.add_argument('mode');args=ap.parse_args()
    s=make_workspace(args.workspace);jobs.assess(s,assessment(s));stub_ready_package(s)
    a,g,r=authorized_preparation(s)
    print(json.dumps({'application_id':a['id'],'review':r,'pdf_path':str(s.root/'packages/demo-job/resume.pdf')}))
