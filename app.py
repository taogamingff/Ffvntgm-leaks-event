import json
import gzip
import requests
import urllib3
from flask import Flask, request, jsonify
from flask_cors import CORS
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import blackboxprotobuf

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
app.json.sort_keys = False
CORS(app)

AeSkEy = b'Yg&tc%DEuh6%Zc^8'
AeSiV = b'6oyZDr22E3ychjM%'

REGIONS = {
    "IND": {"name": "India", "server": "https://client.ind.freefiremobile.com/", "lang": "en-in"},
    "ME": {"name": "Middle East", "server": "https://clientbp.ggpolarbear.com/", "lang": "en-me"},
    "BD": {"name": "Bangladesh", "server": "https://clientbp.ggpolarbear.com/", "lang": "en-bd"},
    "PK": {"name": "Pakistan", "server": "https://clientbp.ggpolarbear.com/", "lang": "en-pk"},
    "BR": {"name": "Brazil", "server": "https://client.us.freefiremobile.com/", "lang": "pt-br"},
    "ID": {"name": "Indonesia", "server": "https://clientbp.ggpolarbear.com/", "lang": "id-id"},
    "TH": {"name": "Thailand", "server": "https://clientbp.ggpolarbear.com/", "lang": "th-th"}
}

CREDENTIALS = {
    "IND":[{"uid": "4789977263", "password": "SPAM-XV87X3FJ"}, {"uid": "4789978667", "password": "SPAM-6RLXJR1O"}],
    "ME":[{"uid": "4760349320", "password": "T10-DEV-AROMJJ3T"}, {"uid": "4760350241", "password": "T10-DEV-PUQWZ19N"}],
    "BD":[{"uid": "4795961625", "password": "T10-DEV-130ECM3D"}, {"uid": "4795959964", "password": "T10-DEV-GLAPP8ZM"}],
    "PK":[{"uid": "4795969768", "password": "T10-DEV-3M1IZHSJ"}, {"uid": "4795977645", "password": "T10-DEV-NCJGNXLA"}],
    "BR":[{"uid": "4775632789", "password": "SUELDO-KXEOVE4Z"}, {"uid": "4775639658", "password": "SUELDO-OKSQ4TV8"}],
    "ID":[{"uid": "4760425239", "password": "T10-DEV-7EOSGBQV"}, {"uid": "4760425261", "password": "T10-DEV-GU25UEI8"}],
    "TH":[{"uid": "4760428808", "password": "T10-DEV-GH7POKVM"}, {"uid": "4760429522", "password": "T10-DEV-L9KBVCQX"}]
}

def enc(d):
    return AES.new(AeSkEy, AES.MODE_CBC, AeSiV).encrypt(pad(d, 16))

def dec(d):
    try:
        return unpad(AES.new(AeSkEy, AES.MODE_CBC, AeSiV).decrypt(d), 16)
    except Exception:
        return d

def smart_encode(payload_dict):
    typedef = {}
    for key, value in payload_dict.items():
        if isinstance(value, int):
            typedef[str(key)] = {'type': 'int', 'name': ''}
        elif isinstance(value, str):
            typedef[str(key)] = {'type': 'bytes', 'name': ''}
        elif isinstance(value, dict):
            _, inner_typedef = blackboxprotobuf.decode_message(blackboxprotobuf.encode_message(value, {}))
            typedef[str(key)] = {'type': 'message', 'message_typedef': inner_typedef, 'name': ''}
        else:
            typedef[str(key)] = {'type': 'int', 'name': ''}
    return blackboxprotobuf.encode_message(payload_dict, typedef)

def decode_bytes(val):
    if isinstance(val, bytes):
        try:
            return val.decode('utf-8')
        except UnicodeDecodeError:
            return val.hex()
    return val

def get_jwt_token(session, uid, password):
    url = f"https://spidey-jwt-gen.vercel.app/guest?uid={uid}&password={password}"
    try:
        response = session.get(url, timeout=6)
        if response.status_code == 200:
            return response.json().get("token")
    except Exception:
        pass
    return None

@app.route('/')
def api_documentation():
    docs = {
        "status": "Online",
        "endpoints": {
            "default_events": {
                "url": "/events",
                "method": "GET",
                "description": "Fetch upcoming events for the default region (IND)"
            },
            "region_events": {
                "url": "/events?region={region_code}",
                "method": "GET",
                "description": "Fetch upcoming events for a specific region"
            }
        },
        "available_regions": {k: v["name"] for k, v in REGIONS.items()},
        "example_response": {
            "region": "IND",
            "total_events": 1,
            "events":[
                {
                    "event_id": 20100,
                    "event_name": "Eclipse Rider",
                    "start_timestamp": 1778365800,
                    "redirect_url": "V2_category_5_groupID_955271",
                    "image_url": "https://dl-tata.freefireind.in/common/Local/IND/config/1750x1070_EclipseRiderMissionSplashIND_en.jpg"
                }
            ]
        }
    }
    return jsonify(docs)

@app.route('/events')
def get_splash_events():
    query = request.args.get('region', 'IND').strip().upper()
    target_region = None
    
    for code, data in REGIONS.items():
        if query == code or query == data["name"].upper():
            target_region = code
            break
            
    if not target_region:
        return jsonify({"error": f"Region '{query}' not found. Available regions: {', '.join(REGIONS.keys())}"}), 404
            
    r_data = REGIONS[target_region]
    accounts = CREDENTIALS.get(target_region,[])

    if not accounts:
        return jsonify({"error": f"Credentials missing for region {target_region}"}), 500

    session = requests.Session()
    jwt_token = None
    
    for acc in accounts:
        jwt_token = get_jwt_token(session, acc["uid"], acc["password"])
        if jwt_token:
            break

    if not jwt_token:
        return jsonify({"error": "Failed to get JWT token after trying all available accounts."}), 401

    game_headers = {
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 11; SM-S908E Build/TP1A.220624.014)",
        "X-GA": "v1 1",
        "X-Unity-Version": "2018.4.11f1",
        "ReleaseVersion": "OB53",
        "Content-Type": "application/octet-stream",
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip",
        "Authorization": f"Bearer {jwt_token}"
    }

    url = f"{r_data['server'].rstrip('/')}/LoginGetSplash"
    payload_dict = {"1": r_data["lang"], "2": 1}
    
    try:
        binary_payload = smart_encode(payload_dict)
        encrypted_req = enc(binary_payload)
        
        r = session.post(url, headers=game_headers, data=encrypted_req, timeout=10, verify=False)
        
        decrypted = dec(r.content)
        
        if decrypted.startswith(b'\x1f\x8b'):
            decrypted = gzip.decompress(decrypted)

        decoded_dict, _ = blackboxprotobuf.decode_message(decrypted)
        
        extracted_events =[]
        detected_region = target_region

        if '2' in decoded_dict and '1' in decoded_dict['2']:
            raw_events = decoded_dict['2']['1']
            
            if isinstance(raw_events, dict):
                raw_events = [raw_events]
                
            for ev in raw_events:
                if '1' in ev:
                    detected_region = decode_bytes(ev['1'])
                
                clean_event = {
                    "event_id": decode_bytes(ev.get('3', 0)),
                    "event_name": decode_bytes(ev.get('4', '')),
                    "start_timestamp": decode_bytes(ev.get('6', 0)),
                    "redirect_url": decode_bytes(ev.get('12', '')),
                    "image_url": decode_bytes(ev.get('14', ''))
                }
                extracted_events.append(clean_event)

        response_data = {
            "region": detected_region,
            "total_events": len(extracted_events),
            "events": extracted_events
        }

        return jsonify(response_data)

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)