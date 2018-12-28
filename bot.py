import urllib.request
while True:
	req = urllib.request.Request("http://0.0.0.0/worker")
	res = urllib.request.urlopen(req)
	print("E' successo qualcosa")

