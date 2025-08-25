import json, requests
API="http://127.0.0.1:8000/ask"
tests=json.load(open("tests/sample_questions.json"))
ok=0
for t in tests:
    r=requests.post(API,json={"question":t["q"]}).json()
    cites=set(r.get("citations",[]))
    miss=[x for x in t["must_include"] if x not in cites]
    print("Q:", t["q"])
    print("  miss:", miss or "OK")
    if not miss: ok+=1
print(f"\n{ok}/{len(tests)} passed")
