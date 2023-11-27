from os import path

if not path.exists('./data'):
  import subprocess
  subprocess.run(['./fetch-data.sh'])

import json

from haystack.nodes import PreProcessor
from haystack.document_stores import OpenSearchDocumentStore
from os import listdir
from os.path import isfile, join

import urllib3
urllib3.disable_warnings()


def read_json(basepath):
    """Process already formatted JSON"""
    files = [join(basepath, f) for f in listdir(basepath) if isfile(join(basepath, f))]
    data = []
    for file in files:
        print(f"Ingesting: {file}")
        with open(file, 'r') as f:
            data.extend(json.load(f))
    return data


def format_doc(doc):
    """Normalize doc to haystack format"""
    content = doc.pop('content')
    return {
      'content': content, 
      'meta': {**doc}
    }


def normalize_doc_list(document_list):
    return [ format_doc(doc) for doc in document_list ]


def index_docs(docs):
    """Push docs to docstore"""
    docstore = OpenSearchDocumentStore(
      **{
        'host': "localhost",
        'port': 9200,
        'verify_certs': False,
        'scheme': "https",
        'username': "admin",
        'password': "admin",
      }
    )
    try: 
      docstore.write_documents(docs, index="docbot")
    except:
        pass


def ingest_docs(split_length=200, split_overlap=20, basepath="data"):
    """Read and normalize doc json before writing them to OpenSearch"""
    raw_docs = read_json(basepath)
    normalized = normalize_doc_list(raw_docs)

    preprocessor = PreProcessor (
        clean_empty_lines=True, 
        split_by='word',
        split_respect_sentence_boundary=False,
        split_length=split_length,
        split_overlap=split_overlap
    )

    preprocessed_data = preprocessor.process(
          normalized, 
          preprocessor)

    index_docs(preprocessed_data)


if __name__=="__main__":
    ingest_docs()
