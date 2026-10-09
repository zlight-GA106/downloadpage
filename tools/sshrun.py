#!/usr/bin/env python3
"""Run commands / move files on the deployment host over SSH (paramiko).

Credentials live in tools/deploy.env (git-ignored) or in the environment -
never in this file. See tools/config.py.
"""
import sys, os, argparse, posixpath

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config                                                     # noqa: E402


def connect():
    import paramiko
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    kwargs = {
        "port": config.get_int("DEPLOY_PORT"),
        "username": config.get("DEPLOY_USER"),
        "timeout": 25,
        "allow_agent": False,
    }
    key = config.get("DEPLOY_KEY")
    if key:
        kwargs["key_filename"] = key
        kwargs["look_for_keys"] = True
    elif config.has_password():
        kwargs["password"] = config.get("DEPLOY_PASS")
        kwargs["look_for_keys"] = False
    else:
        # no password configured: fall back to keys / the agent
        kwargs["look_for_keys"] = True

    c.connect(config.get("DEPLOY_HOST"), **kwargs)
    return c


def run(c, cmd, timeout=600):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


def sftp_makedirs(sftp, remote_dir):
    parts, cur = remote_dir.strip("/").split("/"), ""
    for p in parts:
        cur += "/" + p
        try:
            sftp.stat(cur)
        except IOError:
            sftp.mkdir(cur)
            try:
                sftp.chmod(cur, 0o755)   # ancestors we did not create stay untouched
            except IOError:
                pass
    try:
        sftp.chmod(remote_dir, 0o755)    # some servers drop the execute bit
    except IOError:
        pass


def put_dir(c, local_dir, remote_dir):
    sftp = c.open_sftp()
    sftp_makedirs(sftp, remote_dir)
    n = 0
    for root, dirs, files in os.walk(local_dir):
        rel = os.path.relpath(root, local_dir).replace("\\", "/")
        target = remote_dir if rel == "." else posixpath.join(remote_dir, rel)
        sftp_makedirs(sftp, target)
        for f in files:
            remote = posixpath.join(target, f)
            sftp.put(os.path.join(root, f), remote)
            sftp.chmod(remote, 0o644)
            n += 1
    sftp.close()
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cmd", help="shell command to execute")
    ap.add_argument("--cmdfile", help="file containing the shell command "
                                      "(avoids host-shell quoting problems)")
    ap.add_argument("--put", nargs=2, metavar=("LOCAL", "REMOTE"),
                    help="upload a file or directory")
    ap.add_argument("--get", nargs=2, metavar=("REMOTE", "LOCAL"))
    ap.add_argument("--timeout", type=int, default=600)
    a = ap.parse_args()

    cmd = a.cmd
    if a.cmdfile:
        with open(a.cmdfile, encoding="utf-8") as f:
            cmd = f.read()

    c = connect()
    try:
        if a.put:
            local, remote = a.put
            if os.path.isdir(local):
                n = put_dir(c, local, remote)
                print("uploaded %d file(s) -> %s" % (n, remote))
            else:
                sftp = c.open_sftp()
                sftp_makedirs(sftp, posixpath.dirname(remote))
                sftp.put(local, remote)
                sftp.close()
                print("uploaded %s -> %s" % (local, remote))
        if a.get:
            sftp = c.open_sftp()
            sftp.get(a.get[0], a.get[1])
            sftp.close()
            print("downloaded %s -> %s" % (a.get[0], a.get[1]))
        if cmd:
            rc, out, err = run(c, cmd, a.timeout)
            sys.stdout.write(out)
            if err.strip():
                sys.stderr.write("\n--- STDERR ---\n" + err)
            print("\n[exit %d]" % rc)
            return rc
    finally:
        c.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
