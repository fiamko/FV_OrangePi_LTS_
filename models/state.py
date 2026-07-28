import threading


# Poslední přijatá a dopočtená data pro dashboard.
current_data = {}

# Zamykání při souběhu Flask route a MQTT vlákna.
data_lock = threading.Lock()
