import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import ResearchRun
from app.workers.runner import run_worker
from conftest import register


def complete(client, headers, settings, endpoint, payload):
    submitted = client.post('/api/v1' + endpoint, json=payload, headers=headers)
    assert submitted.status_code == 202, submitted.text
    job_id = submitted.json()['job_id']
    run_worker(settings, once=True)
    job = client.get(f'/api/v1/jobs/{job_id}', headers=headers)
    assert job.json()['state'] == 'succeeded', job.text
    result = client.get(f'/api/v1/jobs/{job_id}/result', headers=headers)
    assert result.status_code == 200, result.text
    return result.json()


def test_real_research_workflow(client, headers, settings, app):
    generated = complete(client, headers, settings, '/datasets/generate', {'name': 'Research population', 'rows': 1000, 'fraud_rate': .12})
    dataset_id = generated['result']['dataset_id']
    assert generated['result']['validation']['valid']
    assert client.get(f'/api/v1/datasets/{dataset_id}/preview?limit=5', headers=headers).json()['total'] == 1000
    assert len(client.get(f'/api/v1/datasets/{dataset_id}/download?format=csv', headers=headers).text.splitlines()) == 1001
    assert len(client.get(f'/api/v1/datasets/{dataset_id}/download?format=json', headers=headers).json()) == 1000
    trained = complete(client, headers, settings, '/models/train', {'dataset_id': dataset_id, 'algorithm': 'logistic_regression', 'name': 'Validation selected detector'})
    model_id = trained['result']['model_id']
    assert trained['result']['tracking_status'] == 'tracked'
    assert trained['mlflow_run_id']
    scored = complete(client, headers, settings, '/predictions/batch', {'dataset_id': dataset_id, 'model_id': model_id})
    assert scored['result']['scored_rows'] == 1000
    predictions = client.get('/api/v1/predictions?limit=10', headers=headers).json()['items']
    assert len(predictions) == 10 and all(row['ground_truth'] in (0, 1) for row in predictions)
    explained = complete(client, headers, settings, '/analysis', {'analysis': 'shap', 'model_id': model_id, 'prediction_id': predictions[0]['id'], 'samples': 1})
    assert explained['result']['max_additivity_error'] < 1e-5
    assert explained['result']['individual'][0]['transaction_id'] == predictions[0]['transaction_id']
    validated = complete(client, headers, settings, '/analysis', {'analysis': 'validation', 'dataset_id': dataset_id})
    assert validated['result']['valid']
    robust = complete(client, headers, settings, '/robustness/runs', {'dataset_id': dataset_id, 'algorithm': 'logistic_regression', 'seeds': [42]})
    assert len(robust['result']['summary']) == 3
    report = complete(client, headers, settings, '/reports', {'run_id': trained['id'], 'format': 'pdf'})
    downloaded = client.get(f"/api/v1/artifacts/{report['artifact_id']}/download", headers=headers)
    assert downloaded.content.startswith(b'%PDF') and len(downloaded.content) > 5000
    second = TestClient(app)
    other = register(second, 'private-research@example.com')
    other_headers = {'Authorization': 'Bearer ' + other['access_token']}
    assert second.get(f'/api/v1/datasets/{dataset_id}/preview', headers=other_headers).status_code == 404
    assert second.post('/api/v1/models/train', headers=other_headers, json={'dataset_id': dataset_id}).status_code == 404
    assert second.get(f"/api/v1/runs/{trained['id']}", headers=other_headers).status_code == 404
    assert client.get('/api/v1/analytics/overview', headers=headers).json()['activity']


def test_learned_generator_job_and_conditional_generation(client, headers, settings):
    dataset = complete(client, headers, settings, '/datasets/generate', {'name': 'Artificial seed', 'rows': 500, 'fraud_rate': .2})
    learned = complete(client, headers, settings, '/generative-models/train', {'dataset_id': dataset['result']['dataset_id'], 'method': 'tvae', 'epochs': 1})
    gm = learned['result']['generative_model_id']
    generated = complete(client, headers, settings, '/datasets/generate', {'name': 'Learned samples', 'rows': 100, 'fraud_rate': .2, 'method': 'tvae', 'generative_model_id': gm, 'conditions': {'payment_method': 'card'}})
    rows = client.get(f"/api/v1/datasets/{generated['result']['dataset_id']}/download?format=json", headers=headers).json()
    assert len(rows) == 100 and sum(row['is_fraud'] for row in rows) == 20
    assert all(row['payment_method'] == 'card' for row in rows)


def test_stream_is_persisted_bounded_and_stoppable(client, headers):
    created = client.post('/api/v1/streams', json={'max_transactions': 2, 'interval_seconds': 1}, headers=headers)
    assert created.status_code == 201
    stream_id = created.json()['id']
    events = client.get(f'/api/v1/streams/{stream_id}/events', headers=headers)
    assert events.text.count('event: transaction') == 2 and 'event: stopped' in events.text
    state = client.get(f'/api/v1/streams/{stream_id}', headers=headers).json()
    assert state['generated_count'] == 2 and len(state['items']) == 2
    assert state['items'][0]['simulated'] and state['items'][0]['predicted_class'] is None
    assert client.get('/api/v1/dashboard', headers=headers).json()['total_transactions'] == 2
    assert client.post(f'/api/v1/streams/{stream_id}/stop', headers=headers).status_code == 200


def test_manual_prediction_contract_and_unknown_ground_truth(client, headers, settings):
    dataset = complete(client, headers, settings, '/datasets/generate', {'rows': 1000, 'fraud_rate': .1})
    trained = complete(client, headers, settings, '/models/train', {'dataset_id': dataset['result']['dataset_id'], 'algorithm': 'random_forest'})
    model_id = trained['result']['model_id']
    assert client.post('/api/v1/predictions', json={'model_id': model_id, 'features': {'is_fraud': 1}}, headers=headers).status_code == 422
    row = client.get(f"/api/v1/datasets/{dataset['result']['dataset_id']}/preview?limit=1", headers=headers).json()['items'][0]
    from app.research.data import FEATURES
    predicted = client.post('/api/v1/predictions', json={'model_id': model_id, 'features': {key: row[key] for key in FEATURES}}, headers=headers)
    assert predicted.status_code == 200 and predicted.json()['ground_truth'] is None
    session = client.post('/api/v1/streams',json={'model_id':model_id,'max_transactions':2,'interval_seconds':1},headers=headers).json()
    events = client.get(f"/api/v1/streams/{session['id']}/events",headers=headers)
    assert events.text.count('event: transaction') == 2
    history = client.get('/api/v1/predictions?limit=10',headers=headers).json()['items']
    assert sum(item['transaction_id'].startswith('LIVE-SIM') for item in history) == 2
