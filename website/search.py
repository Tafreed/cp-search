from website import app

def add_to_index(index, model):
	if not app.elasticsearch:
		return
	payload = {}
	for field in model.__searchable__:
		payload[field] = getattr(model, field)
	app.elasticsearch.index(index=index, id=model.id, body=payload)

def remove_from_index(index, model):
	if not app.elasticsearch:
		return
	app.elasticsearch.delete(index=index, id=model.id)

def query_index(index, query, page, per_page):
	if not app.elasticsearch:
		return [], 0
	search = app.elasticsearch.search(
		index=index,
		body={'query': {'multi_match': {'query': query, 'fields': ['*']}},'from': (page - 1) * per_page, 'size': per_page})

	ids = [int(hit['_id']) for hit in search['hits']['hits']]
	return ids, search['hits']['total']['value']
		