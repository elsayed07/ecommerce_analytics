import pytest
from rest_framework.test import APIRequestFactory

from apps.common.permissions import IsAdmin, IsAnalyst, IsStaff
from apps.users.models import User

from .factories import UserFactory

pytestmark = pytest.mark.django_db


def _request_for(user):
    request = APIRequestFactory().get("/")
    request.user = user
    return request


def test_role_permissions_match_their_role():
    admin = UserFactory(role=User.Role.ADMIN)
    analyst = UserFactory(role=User.Role.ANALYST)
    staff = UserFactory(role=User.Role.STAFF)

    assert IsAdmin().has_permission(_request_for(admin), None)
    assert IsAnalyst().has_permission(_request_for(analyst), None)
    assert IsStaff().has_permission(_request_for(staff), None)


def test_role_permissions_reject_other_roles():
    staff = UserFactory(role=User.Role.STAFF)

    assert not IsAdmin().has_permission(_request_for(staff), None)
    assert not IsAnalyst().has_permission(_request_for(staff), None)


def test_superuser_satisfies_every_role_gate():
    superuser = UserFactory(role=User.Role.STAFF, is_superuser=True, is_staff=True)

    assert IsAdmin().has_permission(_request_for(superuser), None)
    assert IsAnalyst().has_permission(_request_for(superuser), None)
    assert IsStaff().has_permission(_request_for(superuser), None)


def test_created_superuser_gets_admin_role():
    superuser = User.objects.create_superuser(
        username="root", email="root@example.com", password="pass12345"
    )
    assert superuser.role == User.Role.ADMIN
