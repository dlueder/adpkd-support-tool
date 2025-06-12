import os
import json
from pathlib import Path


class Settings:
    def __init__(self):
        self.home = str(Path.home())
        self.data = dict()
        self.path = os.path.join(self.home, 'adpkd_settings.json')
        print(self.path)

    def get(self, key, default=None):
        if key in self.data:
            return self.data[key]
        return default

    def save(self):
        if self.path:
            with open(self.path, 'w') as f:
                json.dump(self.data, f)
                return True
        return False

    def load(self):
        if os.path.exists(self.path):
            with open(self.path, 'r') as f:
                self.data = json.load(f)
                print(self.data)
                return True
        return False

    def reset(self):
        if os.path.exists(self.path):
            os.remove(self.path)
            print(f'settings file removed: {self.path}')
        self.data = {}
