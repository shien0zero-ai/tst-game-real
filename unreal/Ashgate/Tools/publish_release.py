"""Package validated Windows artifacts and publish a separate GitHub Release.

Uses the existing Git credential helper in memory; never prints credentials.
Does not install software or alter Git/Windows authentication settings.
"""
import argparse, hashlib, http.client, json, pathlib, subprocess, urllib.error, urllib.parse, urllib.request, zipfile

ROOT=pathlib.Path(__file__).resolve().parents[3]
PROJECT=ROOT/"unreal/Ashgate"
REPOSITORY="shien0zero-ai/tst-game-real"

def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--publish",action="store_true",help="Create a GitHub Release and upload the ZIP and SHA256")
    p.add_argument("--tag",default="ue5-prototype-2026-11-12-r2")
    args=p.parse_args()
    commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    status=subprocess.check_output(["git","status","--porcelain"],cwd=ROOT,text=True)
    if status.strip(): raise RuntimeError("Commit the reviewed source and validation report before packaging a release")
    for name in ("PIE-QA","PackagedQA"):
        log=(PROJECT/"Saved"/(name+".log")).read_text(encoding="utf-8",errors="replace")
        if "QA COMPLETE failures=0" not in log or "QA FAIL:" in log:
            raise RuntimeError(name+" has not passed")
        if "Failed to compile Material" in log or "Fatal error" in log:
            raise RuntimeError(name+" contains an unresolved rendering error")
    package=ROOT/"work/ue5-package/Windows"
    binary=package/"Ashgate/Binaries/Win64/Ashgate.exe"
    if not binary.is_file() or not (package/"Ashgate.exe").is_file(): raise RuntimeError("Windows package missing")
    output=ROOT/"work/releases"; output.mkdir(parents=True,exist_ok=True)
    archive=output/"Ashgate-UE5-Prototype-Windows-x64.zip"
    info={"game":"ASHGATE / DEPOT 04 - UE5 prototype","source_commit":commit,"engine":"5.8.4","configuration":"Development","platform":"Windows x64 / D3D12","msvc":"14.52.37029","sdk":"10.0.26100.0","binary_sha256":digest(binary),"qa":"PIE and packaged world checks passed; see VALIDATION.md for input and visual limits"}
    prefix="Ashgate-UE5-Prototype/"
    with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for file in sorted(package.rglob("*")):
            rel=file.relative_to(package)
            if not file.is_file() or "saved" in [part.lower() for part in rel.parts] or file.suffix.lower() in (".pdb",".log"): continue
            z.write(file,prefix+rel.as_posix())
        for file in sorted((ROOT/"licenses").rglob("*.txt")):
            z.write(file,prefix+"licenses/"+file.relative_to(ROOT/"licenses").as_posix())
        for name in ("README.md","ART-NOTES.md","VALIDATION.md"):
            if (PROJECT/name).is_file(): z.write(PROJECT/name,prefix+name)
        z.writestr(prefix+"build-info.json",json.dumps(info,ensure_ascii=False,indent=2)+"\n")
    with zipfile.ZipFile(archive) as z:
        if z.testzip(): raise RuntimeError("ZIP integrity check failed")
        if any("/Saved/" in n or n.endswith(".pdb") for n in z.namelist()): raise RuntimeError("User data/debug symbols unexpectedly included")
    checksum=archive.with_suffix(".zip.sha256")
    checksum.write_text(digest(archive)+"  "+archive.name+"\n",encoding="ascii")
    print("Validated ZIP:",archive,"bytes:",archive.stat().st_size)
    if not args.publish: return
    creds=subprocess.run(["git","-c","credential.interactive=never","credential","fill"],cwd=ROOT,input="protocol=https\nhost=github.com\n\n",text=True,capture_output=True,check=True)
    fields=dict(line.split("=",1) for line in creds.stdout.splitlines() if "=" in line)
    token=fields.get("password")
    if not token: raise RuntimeError("No existing GitHub credential available")
    headers={"Authorization":"Bearer "+token,"User-Agent":"Ashgate-release-tool","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}
    def api(method,path,data=None):
        request=urllib.request.Request("https://api.github.com/repos/"+REPOSITORY+path,data=None if data is None else json.dumps(data).encode(),headers=headers,method=method)
        if data is not None: request.add_header("Content-Type","application/json")
        with urllib.request.urlopen(request,timeout=60) as r: return json.load(r)
    try: release=api("GET","/releases/tags/"+args.tag)
    except urllib.error.HTTPError as e:
        if e.code!=404: raise RuntimeError("Release lookup HTTP "+str(e.code)) from None
        release=api("POST","/releases",{"tag_name":args.tag,"target_commitish":commit,"name":"ASHGATE / DEPOT 04 - UE5 playable prototype","body":"UE5 5.8.4 / Windows x64 Development prototype. Extract the ZIP and run Ashgate.exe. Separate from the existing Godot edition. Includes M1911 attribution and third-party credits.\n\nValidated on the local RTX 5080 PC: Editor build, real PIE, packaged game checks, screenshots and input probe. See unreal/Ashgate/VALIDATION.md at commit "+commit+" for measured results and remaining limitations. Graphics and AI are an early prototype; Bodycam-level visuals are not yet achieved.","prerelease":True,"draft":False})
    if release.get("target_commitish") not in (commit,"main"):
        raise RuntimeError("Existing release points to another source; choose a new tag")
    existing={a["name"] for a in release.get("assets",[])}
    upload=urllib.parse.urlsplit(release["upload_url"].split("{")[0])
    if upload.scheme!="https" or upload.hostname!="uploads.github.com": raise RuntimeError("Unexpected upload host")
    for file in (archive,checksum):
        if file.name in existing: raise RuntimeError("Refusing to overwrite existing release asset "+file.name)
        connection=http.client.HTTPSConnection(upload.hostname,timeout=180)
        path=upload.path+"?name="+urllib.parse.quote(file.name)
        connection.putrequest("POST",path)
        for key,value in headers.items(): connection.putheader(key,value)
        connection.putheader("Content-Type","application/zip" if file.suffix==".zip" else "text/plain")
        connection.putheader("Content-Length",str(file.stat().st_size)); connection.endheaders()
        with file.open("rb") as f:
            for block in iter(lambda:f.read(1024*1024),b""): connection.send(block)
        response=connection.getresponse(); body=response.read(); connection.close()
        if response.status!=201: raise RuntimeError("Asset upload HTTP "+str(response.status))
        print("Uploaded",json.loads(body)["browser_download_url"])
    print("Release:",release["html_url"])
    if args.tag=="ue5-prototype-2026-11-12-r2":
        for tag in ("ue5-prototype-2026-11-12","ue5-prototype-2026-11-12-r1"):
            old=api("GET","/releases/tags/"+tag)
            notice="Superseded by "+release["html_url"]+" . r2 uses rendered HUD hitboxes, validates press/release on the same button, requires quit confirmation, and was tested after extracting the ZIP with the production save path and default fullscreen settings.\n\n"
            api("PATCH","/releases/"+str(old["id"]),{"body":notice+old.get("body","")})

if __name__=="__main__": main()
