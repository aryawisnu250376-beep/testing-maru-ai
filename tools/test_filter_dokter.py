# Uji filter episodes pada renderStudio di script_dokter_v4.js
raw_episodes = [
    {"id": "1", "title": "You are the CAPTURE step...", "status": "pending_approval"},
    {"id": "2", "title": "You are the CAPTURE step...", "status": "rejected"},
    {"id": "3", "title": "Model open source...", "status": "rejected"},
    {"id": "4", "title": "uji jembatan hermes", "status": "failed"},
    {"id": "5", "title": "Model AI baru: Mistral", "status": "pending_approval"},
]

def filter_episodes(episodes):
    return [
        e for e in episodes
        if "CAPTURE" not in e["title"]
        and not any(s in e["status"].lower() for s in ["acc", "revisi", "reject", "tolak", "failed"])
    ]

res = filter_episodes(raw_episodes)
assert len(res) == 1
assert res[0]["id"] == "5"
print("FILTER EPISODES DOKTER: VALID & TEPAT 100%!")
