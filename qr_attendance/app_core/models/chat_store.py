import os
import json

STORE = os.path.join(os.getcwd(), 'models', 'chat_history.json')
os.makedirs(os.path.dirname(STORE), exist_ok=True)

def append_chat(item):
    """item: {'question':..., 'answer':...}"""
    try:
        arr = []
        if os.path.exists(STORE):
            with open(STORE, 'r', encoding='utf-8') as f:
                arr = json.load(f)
        arr.append({'q': item.get('question'), 'a': item.get('answer')})
        with open(STORE, 'w', encoding='utf-8') as f:
            json.dump(arr[-200:], f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(str(e))
