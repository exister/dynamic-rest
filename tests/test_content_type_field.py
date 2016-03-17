import json

from rest_framework.test import APITestCase

from dynamic_rest.routers import DynamicRouter
from tests.models import Zebra
from tests.setup import create_fixture


class TestContentTypeFieldAPI(APITestCase):

    def setUp(self):
        self.fixture = create_fixture()
        f = self.fixture
        f.users[0].favorite_pet = f.cats[0]
        f.users[0].save()

        f.users[1].favorite_pet = f.cats[1]
        f.users[1].save()

        f.users[2].favorite_pet = f.dogs[1]
        f.users[2].save()

    def test_id_only(self):
        """
        In the id_only case, the favorite_pet field looks like:

        ```
            "favorite_animal" : {
                "type": "cats",
                "id": "1"
            }
        ```
        """
        url = (
            '/users/?include[]=favorite_pet'
            '&filter{favorite_pet_id.isnull}=false'
        )
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        content = json.loads(response.content.decode('utf-8'))
        self.assertTrue(
            all(
                [_['favorite_pet'] for _ in content['users']]
            )
        )
        self.assertFalse('cats' in content)
        self.assertFalse('dogs' in content)
        self.assertTrue('type' in content['users'][0]['favorite_pet'])
        self.assertTrue('id' in content['users'][0]['favorite_pet'])

    def test_sideload(self):
        url = (
            '/users/?include[]=favorite_pet.'
            '&filter{favorite_pet_id.isnull}=false'
        )
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        content = json.loads(response.content.decode('utf-8'))
        self.assertTrue(
            all(
                [_['favorite_pet'] for _ in content['users']]
            )
        )
        self.assertTrue('cats' in content)
        self.assertEqual(2, len(content['cats']))
        self.assertTrue('dogs' in content)
        self.assertEqual(1, len(content['dogs']))
        self.assertTrue('type' in content['users'][0]['favorite_pet'])
        self.assertTrue('id' in content['users'][0]['favorite_pet'])

    def test_query_counts(self):
        # NOTE: Django doesn't seem to prefetch ContentType objects
        #       themselves, and rather caches internally. That means
        #       this call could do 5 SQL queries if the Cat and Dog
        #       ContentType objects haven't been cached.
        with self.assertNumQueries(3):
            url = (
                '/users/?include[]=favorite_pet.'
                '&filter{favorite_pet_id.isnull}=false'
            )
            response = self.client.get(url)
            self.assertEqual(200, response.status_code)

        with self.assertNumQueries(3):
            url = '/users/?include[]=favorite_pet.'
            response = self.client.get(url)
            self.assertEqual(200, response.status_code)

    def test_unknown_resource(self):
        """Test case where polymorhpic relation pulls in an object for
        which there is no known canonical serializer.
        """

        zork = Zebra.objects.create(
            name='Zork',
            origin='San Francisco Zoo'
        )

        user = self.fixture.users[0]
        user.favorite_pet = zork
        user.save()

        self.assertIsNone(DynamicRouter.get_canonical_serializer(Zebra))

        url = '/users/%s/?include[]=favorite_pet' % user.pk
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        content = json.loads(response.content.decode('utf-8'))
        self.assertTrue('user' in content)
        self.assertFalse('zebras' in content)  # Not sideloaded
        user_obj = content['user']
        self.assertTrue('favorite_pet' in user_obj)
        self.assertEqual('Zebra', user_obj['favorite_pet']['type'])
        self.assertEqual(zork.pk, user_obj['favorite_pet']['id'])
