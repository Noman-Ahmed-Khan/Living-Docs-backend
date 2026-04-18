from app.domain.users.entities import User
from app.infrastructure.database.repositories.user_repository import SQLUserRepository


def test_user_repository_round_trip_preserves_full_name():
    user = User.create(
        email="jane@example.com",
        hashed_password="hashed-password",
        full_name="Jane Doe",
        require_verification=False,
    )

    model = SQLUserRepository._to_model(user)

    assert model.full_name == "Jane Doe"

    round_tripped = SQLUserRepository._to_entity(model)
    assert round_tripped.full_name == "Jane Doe"
