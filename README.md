# Conversation Architecting Toolkit

Welcome to what I am dubbing as the Conversation Architecting Toolchain for OpenSearch (CAT for short). Why not call this Retrevial Augmented Generation (RAG) like everyone else? Because that is merely one of the tools used in a conversation architecture. These systems have far more moving parts than the term RAG can cover.


## Pre-requisites

Lets dive into the demo! First you will need to spin up a OpenSearch and OpenSearch Dashboards container on your local machine. We've included a docker compose file that can be started in this repo by running. 

```bash
docker compose up -d
```

Once those have started you should be able to access OpenSearch Dashboards by going to: [https://localhost:5601](https://localhost:5601) in your web browser. The login is going to be **username:** `admin` and **password:** `admin`. Once in select dismiss and dismiss. Then you can go to **Dev Tools** in the upper right section of the screen.

Additionaly, this demo assumes you have a **production** API key for [Cohere](https://cohere.com/) and an API key for [OpenAI](https://openai.com/). Please note a production key for Cohere will incur costs and it's only recomennded that you proceed if you are aware with what those costs will be. Running the demo at the time of me writing this incurred $0.07 USD however, your experience may be different. 


## Cluster settings

There are a few [cluster settings](https://opensearch.org/docs/latest/ml-commons-plugin/cluster-settings/) we need to apply to get started. These specify where models can run (on any node), what model URL's are accessible (Cohere and OpenAI), and turns on the experimental RAG and Conversational Memory Feature. 

```
PUT /_cluster/settings
{
    "persistent": {
        "plugins.ml_commons.allow_registering_model_via_url": true,
        "plugins.ml_commons.only_run_on_ml_node": false,
        "plugins.ml_commons.connector_access_control_enabled": true,
        "plugins.ml_commons.model_access_control_enabled": true,
        "plugins.ml_commons.memory_feature_enabled": true,
        "plugins.ml_commons.rag_pipeline_feature_enabled": true,
        "plugins.ml_commons.trusted_connector_endpoints_regex": [
          "^https://api\\.cohere\\.ai/.*$",
          "^https://api\\.openai\\.com/.*$"
        ]
    }
}
```


## Create model group

After we have applied the cluster settings we will need a [model group](https://opensearch.org/docs/latest/ml-commons-plugin/model-access-control/#model-groups). This controlls which accounts can access our models. 

> Note, several of these steps have a `#` at the end followed by a constant looking name. We will use these to track our parameters for this demo. After you run the step you should track the ouput ID in these as we will need to paste them into other steps later.

```
POST /_plugins/_ml/model_groups/_register
{
    "name": "Model_Group",
    "description": "Public ML Model Group",
    "access_mode": "public"
}
# MODEL_GROUP_ID: 
```


## Register and deploy the text embedding model

Now that we have a model group we should probably take a step back and talk about why we are even using machine learning (ML) models in the first place and... which models? The type of ML models we turn text into an embedding (an array of floating point numbers). 

These embeddings can be used for several different things such as classifying documents. We are interested in a type of embeddings that are used to calculate "semantic similarity". To put it plainly, semantic simiarity, is a way of measuring how closeley two documents may be related. For example, while "He used his golf driver" and "He was a F1 driver" might have a lot of the same words we know that they are talking about extremely different topics.

I won't be able to cover all the different embeddings what I can say is we are going to be using [Cohere's Embed-v3](https://txt.cohere.com/introducing-embed-v3/) model.

> Remember that `MODEL_GROUP_ID` we saved earlier? This is where we will need it. Replace the `<MODEL_GROUP_ID>` in the below section with the actual ID. This will look something like the following: ` "model_group_id": "w4oria34roa9ajo4jiaj",`. Do the same with your Cohere production key. Don't forget to save the output of this step in the `EMBEDDING_MODEL_ID` below!

```
POST /_plugins/_ml/models/_register?deploy=true
{
    "name": "embed-english-v3.0",
    "function_name": "remote",
    "description": "Cohere model for embedding",
    "model_group_id": "<MODEL_GROUP_ID>",
    "connector": {
      "name": "Cohere Connector",
      "description": "Cohere model for Embeddings",
      "version": "1.0",
      "protocol": "http",
      "credential": {
             "cohere_key": "<COHERE_KEY>"
         },
      "parameters": {
        "model": "embed-english-v3.0",
        "truncate": "END"
      },
      "actions": [{
         "action_type": "predict",
         "method": "POST",
         "url": "https://api.cohere.ai/v1/embed",
         "headers": {
                 "Authorization": "Bearer ${credential.cohere_key}"
             },
  			"request_body": "{ \"texts\": ${parameters.texts}, \"truncate\": \"${parameters.truncate}\", \"model\": \"${parameters.model}\", \"input_type\": \"search_document\" }",
  			"pre_process_function": "connector.pre_process.cohere.embedding",
			  "post_process_function": "connector.post_process.cohere.embedding"
     }]
  }
}
# EMBEDDING_MODEL_ID:
```


## Create ingestion pipeline

After we have our embedding model registered we can create our ingestion pipeline. This pipeline will allow us to ingest text data from the `content` field and will automatically create `content_embedding`s that we can use for semantic search later. This uses the Cohere model from above. 

```
PUT _ingest/pipeline/embedding-ingest-pipeline
{
  "description": "Neural Search Pipeline",
  "processors" : [
    {
      "text_embedding": {
        "model_id": "<EMBEDDING_MODEL_ID>",
        "field_map": {
          "content": "content_embedding"
        }
      }
    }
  ]
}
```


## Register and deploy the language model

Next, we will be registering the large language model (LLM) we will be using to generate our output. We will be using GPT-3.5-Turbo as it's well known and performs well in a variety of situations. 

```
POST /_plugins/_ml/models/_register?deploy=true
{
    "name": "gpt-3.5-turbo",
    "function_name": "remote",
    "description": "OpenAI Chat Connector",
    "model_group_id": "<MODEL_GROUP_ID>",
    "connector": {
      "name": "OpenAI Chat Connector",
      "description": "The connector to public OpenAI model service for GPT 3.5",
      "version": 1,
      "protocol": "http",
      "parameters": {
          "endpoint": "api.openai.com",
          "model": "gpt-3.5-turbo"
      },
      "credential": {
          "openAI_key": "<OPENAI_KEY>"
      },
      "actions": [
          {
              "action_type": "predict",
              "method": "POST",
              "url": "https://${parameters.endpoint}/v1/chat/completions",
              "headers": {
                  "Authorization": "Bearer ${credential.openAI_key}"
              },
              "request_body": "{ \"model\": \"${parameters.model}\", \"messages\": ${parameters.messages} }"
          }
      ]
  }
}
# LLM_MODEL_ID:  
```

## Configure the RAG search pipeline

Much like our ingestion pipeline this will allow us to automatically have several things happen every time we perform a search. The first is to create a results processor `phase_results_processor`. This post-processing step in our search pipeline  enables us to do a [hybrid search](https://opensearch.org/docs/latest/search-plugins/search-pipelines/normalization-processor/#score-normalization-and-combination). Here we are going to retrieve documents using a vector search and with BM25 (commonly called keyword search) and combine the results. The primary purpose of this is to normalize the relevance scores as they use different scales. 

The second, post-processing step is the "retrieval_augmented_generation" step. This is our RAG step which takes the results and feed them to a language model as context for answering the question.

```
PUT _search/pipeline/rag-search-pipeline
{
  "phase_results_processors": [
    {
      "normalization-processor": {
        "normalization": {
          "technique": "min_max"
        },
        "combination": {
          "technique": "arithmetic_mean",
          "parameters": {
            "weights": [
              0.3,
              0.7
            ]
          }
        }
      }
    }
  ],
  "response_processors": [
    {
      "retrieval_augmented_generation": {
        "description": "RAG search pipeline to be used with Cohere index",
        "model_id": "<LLM_MODEL_ID>",
        "context_field_list": ["content"],
        "system_prompt": "You are a helpful OpenSearch assistant called DocBot",
        "user_instructions": "Answer the following question using only the provided context. If the provided context does not provide enough information to answer the question respond with something along the lines of 'I dont have enough information to answer that.'"
      }
    }
  ]
}
```


## Create KNN index 

Now that we have our pipeline for ingesting and searching we can finally create our index. In our index, we specify it needs to use our ingestion pipeline, search pipeline, and we provide it the parameters for our ML model. These should be documented somewhere on the model either in the `config.json` or a similar format.  

> Note you need to match `space_type` to model space. eg embed-english-v3.0 recommends cosine similarity for comparing embeddings. 

```
PUT /docbot
{
	"settings": {
		"index.knn": true,
		"default_pipeline": "embedding-ingest-pipeline",
    "index.search.default_pipeline": "rag-search-pipeline"
	},
	"mappings": {
		"properties": {
			"content_embedding": {
				"type": "knn_vector",
				"dimension": 1024,
				"method": {
					"name": "hnsw",
					"space_type": "cosinesimil",
					"engine": "nmslib"
				}
			},
			"content": {
				"type": "text"
			}
		}
	}
}
```

## Overview

Lets take a look really quick at what we have configured so far!

### Ingest

The first part is the ingestion pipeline. With this in place we can upload docs using our normal `_bulk` endpoints. It will automatically create embeddings of our `content` field and ingest them into our search index. Our search index is equipped to do both traditional search (BM25) and vector search (using nmslib and Cohere Embed-v3).

![Ingestion Pipeline](/diagrams/RAGE_Search_Ingest.svg)

### Search

Then, on the search side we have configured a search post-processor that will merge our two result sets (the one from the BM25 and the one from the vector search). Then it will hand those results off to our RAG processor which will generate our response using the provided context. Do not worry about the pre-processor or conversational search steps just yet as we define those in our query. 

![Search Pipeline](/diagrams/RAGE_Search_Search.svg)


## Hydrate index with `_bulk`

Now that we have all this infrastructure lets do something with it! Below is just a sample of how we can upload data. We are not actually going to use that today. Pass to the next code block where we will actually run some code to populate our index. 

```
POST _bulk
{ "create" : { "_index" : "docbot", "_id" : "1" }}
{ "content":"Testing neural search"}
{ "create" : { "_index" : "docbot", "_id" : "2" }}
{ "content": "What are we doing"}
{ "create" : { "_index" : "docbot", "_id" : "3" } }
{ "content": "This should exist"}
```

```
python -m pip install -r requirements.txt
python ingestion.py
```

This will break all the documents from OpenSearch's documentation and website into smaller chunks (150 words) that makes it better for retrieving and providing as context. The details of this script are out of scope for this already long demo 😅


## Create a conversation

Now we will create a conversation. This will allow GPT to have context from our previous messages in our conversation. 

```
POST /_plugins/_ml/memory/conversation
{
  "name": "DocBot Conversation"
}
# CONVERSATION_ID: 
```


## Search and generate response

Everything has led to this moment. While this is executed as one request it does three distinct things. First, it will pre-process our text for our vector search. This is why we are providing the `EMBEDDING_MODEL_ID` in the `neural` section. 

Next, it will execute a hybrid search that will retrieve documents using BM25 and vector search. These results will be combined after they have executed by our post-processor. 

Finally, it will pass the parameters to the RAG post processor. This instructs it to generate the response using the conversation history and the documents it's found in the hybrid search. 

```
GET /cohere-index/_search
{
  "_source": {
    "exclude": [
      "content_embedding"
    ]
  },
  "query": {
    "hybrid": {
      "queries": [
        {
          "match": {
            "content": {
              "query": <QUESTION>
            }
          }
        },
        {
          "neural": {
            "content_embedding": {
              "query_text": <QUESTION>,
              "model_id": "<EMBEDDING_MODEL_ID>",
              "k": 5
            }
          }
        }
      ]
    }
  },
  "ext": {
		"generative_qa_parameters": {
      "llm_model": "gpt-3.5-turbo",
			"llm_question": <QUESTION>,
			"conversation_id": "<CONVERSATION_ID>",
                         "context_size": 3,
                         "interaction_size": 3,
                         "timeout": 45
		}
	}
}
```


## Cleanup
```
POST /_plugins/_ml/models/<EMBEDDING_MODEL_ID>/_undeploy
DELETE /_plugins/_ml/models/<EMBEDDING_MODEL_ID>
POST /_plugins/_ml/models/<LLM_MODEL_ID>/_undeploy
DELETE /_plugins/_ml/models/<LLM_MODEL_ID>
DELETE _ingest/pipeline/cohere-ingest-pipeline
DELETE _search/pipeline/rag-search-pipeline
DELETE /_plugins/_ml/memory/conversation/<CONVERSATION_ID>
DELETE cohere-index
```

### Troubleshoot:
```
POST /_plugins/_ml/models/<MODEL_ID>/_predict
{
  "parameters": {
    "texts": ["This should exist"]
  }
}
```



GET /cohere-index/_search?search_pipeline=_none
```
{
  "query": {
    "match_all": {}
  }
}
``````