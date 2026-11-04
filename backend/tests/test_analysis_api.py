from test_research_api import complete


def test_analysis_catalog_and_shared_test_model_comparison(client, headers, settings):
    population = complete(client, headers, settings, '/datasets/generate', {'rows':1000,'fraud_rate':.15})
    dataset = population['result']['dataset_id']
    fitted = complete(client, headers, settings, '/models/train', {'dataset_id':dataset,'algorithm':'random_forest'})
    model = fitted['result']['model_id']
    for analysis in ['quality','drift','patterns','risk','imbalance','noise','unseen','performance','importance','permutation']:
        result = complete(client, headers, settings, '/analysis', {'dataset_id':dataset,'reference_dataset_id':dataset,'model_id':model,'analysis':analysis,'samples':2,'levels':[.05,.1]})
        assert result['result']['run_id']
    second = complete(client, headers, settings, '/models/train', {'dataset_id':dataset,'algorithm':'logistic_regression'})
    compared = client.post('/api/v1/models/comparison',json={'model_ids':[model,second['result']['model_id']]},headers=headers)
    assert compared.status_code == 200 and len(compared.json()['items']) == 2
    assert client.get('/api/v1/scenarios/catalog',headers=headers).json()['items']
