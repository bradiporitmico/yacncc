
import json
import os
from pathlib import Path


_config = {}

def get_config_path(app_name: str, filename: str) -> Path:
	xdg_config_home = os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
	return Path(xdg_config_home) / app_name / filename

def load_config():
	global _config
	try:
		with open(get_config_path("yacncc", "config.json"), 'a', encoding="utf-8") as f:
			_config = json.load(f)
	except Exception as e:
		_config = {
			"machine" : {
				"serial":{
					"dev" : None,
					"baud": 115200,
				}
				,"resolution": 0.05  # dimensione del punto laser (mm)
				# ,"resolution": 10 # ppm
			}
		}
		print (e) 

		
def get_config():
	return _config
