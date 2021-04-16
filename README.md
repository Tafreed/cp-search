Installation:-

# Flask and related compoments

In the cp_search_engine folder, enter the following in the terminal or powershell:-

pip install -r requirements.txt



# Elastisearch

Install Elastisearch using the links given as follows for Windows and Linux:-

Linux:-
https://linuxize.com/post/how-to-install-elasticsearch-on-ubuntu-18-04/

Windows:-
https://www.elastic.co/guide/en/elasticsearch/reference/current/zip-windows.html

After successfully installing elastisearch, enter the following in the terminal or powershell:-

```python
from website.models import Problem
Problem.reindex()
```

This will take a few minutes.

After this is finished, enter the following in the terminal or powershell to run the App:-

```console
python cp_search_engine.py
```
