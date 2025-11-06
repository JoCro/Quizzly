import pytest
from django.conf import settings

pytestmark = pytest.mark.django_db


def access_cookie_name():
    return getattr(settings, 'JWT_ACCESS_COOKIE', 'access_token')


def refresh_cookie_name():
    return getattr(settings, 'JWT_REFRESH_COOKIE', 'refresh_token')


def test_register_success_201(api_client,  csrf_token):
    resp = api_client.post('/api/register/', {
        'username': 'Spongebob',
        'password': 'BikiniBottom42!',
        'confirmed_password': 'BikiniBottom42!',
        'email': 'spongebob@krustycrab.com',
    },
        format='json',
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert resp.status_code == 201
    assert 'detail' in resp.data
    assert 'success' in resp.data['detail'].lower(
    ) or 'created' in resp.data['detail'].lower()


def test_register_bad_data_400(api_client, csrf_token):
    resp = api_client.post('/api/register/', {
        'username': 'bobSponge',
        'password': 'x',
        'confirmed_password': 'y',
        'email': 'bobsponge@example.com'
    },
        format='json',
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert resp.status_code == 400
    assert 'errors' in resp.data or 'detail' in resp.data


def test_login_success_sets_cookies_and_body(api_client, create_user, csrf_token):
    user, pwd = create_user(
        username='carol', email='carol@example.com', password='securePass123!')
    resp = api_client.post('/api/login/', {
        'username': user.username, 'password': pwd},
        format='json',
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert resp.status_code == 200
    assert resp.data.get('detail')
    assert resp.data.get('user', {}).get('username') == user.username
    assert access_cookie_name() in resp.cookies
    assert refresh_cookie_name() in resp.cookies


def test_login_wrong_password_401(api_client, create_user, csrf_token):
    user, _ = create_user(
        username='dave', email='dave@example.com', password='CorrectPasswort1')
    resp = api_client.post(
        '/api/login/',
        {'username': user.username, 'password': 'INCORRECT42'},
        format='json',
        HTTP_X_CSRFTOKEN=csrf_token
    )
    assert resp.status_code == 401


def test_logout_requires_auth_401(api_client, csrf_token):
    resp = api_client.post(
        '/api/logout/', {}, format='json', HTTP_X_CSRFTOKEN=csrf_token)
    assert resp.status_code in (401, 403)


def test_logout_success_clears_cookies(api_client, login_user, csrf_token):
    resp = api_client.post(
        '/api/logout/', {}, format='json', HTTP_X_CSRFTOKEN=csrf_token)
    assert resp.status_code == 200
    set_cookie_headers = ";".join(str(v) for v in resp.cookies.values())
    assert access_cookie_name() in set_cookie_headers
    assert refresh_cookie_name() in set_cookie_headers


def test_refresh_without_cookie_401(api_client, csrf_token):
    resp = api_client.post('/api/token/refresh/', {},
                           format='json', HTTP_X_CSRFTOKEN=csrf_token)
    assert resp.status_code == 401


def test_refresh_with_cookie_200_sets_new_access(api_client, login_user, csrf_token):
    resp = api_client.post('/api/token/refresh/', {},
                           format='json', HTTP_X_CSRFTOKEN=csrf_token)
    assert resp.status_code == 200
    assert resp.data.get('detail') == 'Token refreshed'
    assert resp.data.get('access')
    assert access_cookie_name() in resp.cookies


def test_login_get_sets_csrf_cookie(api_client):
    resp = api_client.get('/api/login/')
    assert resp.status_code == 200
    assert 'csrftoken' in api_client.cookies or 'csrftoken' in resp.cookies


def test_register_duplicate_username_400(api_client, csrf_token, create_user):
    user, _ = create_user(
        username='exists', email='exists@example.com', password="safePasswort1")
    resp = api_client.post(
        '/api/register/',
        {
            'username': user.username,
            'password': 'safePasswort1',
            'confirmed_password': 'safePasswort1',
            'email': 'new@example.com',
        },
        format='json',
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert resp.status_code == 400


def test_register_invalid_email_400(api_client, csrf_token):
    resp = api_client.post(
        '/api/register/',
        {
            'username': 'invalidUsername',
            'password': 'safePasswort1',
            'confirmed_password': 'safePasswort1',
            'email': 'notAnEmail',
        },
        format='json',
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert resp.status_code == 400


def test_login_missing_password_400_or_401(api_client, csrf_token):
    resp = api_client.post(
        '/api/login/',
        {'username': 'nobody'},
        format='json',
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert resp.status_code in (400, 401)


def test_logout_without_csrf_403(api_client, login_user):
    resp = api_client.post('/api/logout/', {}, format='json')
    assert resp.status_code in (403, 401)


def test_refresh_with_invalid_cookie_401(api_client, csrf_token):
    api_client.cookies['refresh_token'] = 'invalid.jwt.token'
    resp = api_client.post('/api/token/refresh/', {},
                           format='json', HTTP_X_CSRFTOKEN=csrf_token)
    assert resp.status_code == 401
