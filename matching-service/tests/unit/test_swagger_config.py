from app.core.config import Settings


def test_swagger_enabled_for_development_alias() -> None:
    settings = Settings(ENVIRONMENT="development", SWAGGER_ENV="DEV")

    assert settings.is_swagger_enabled() is True


def test_swagger_disabled_when_environment_does_not_match_flag() -> None:
    settings = Settings(ENVIRONMENT="production", SWAGGER_ENV="DEV")

    assert settings.is_swagger_enabled() is False


def test_swagger_enabled_for_production_alias() -> None:
    settings = Settings(ENVIRONMENT="production", SWAGGER_ENV="PROD")

    assert settings.is_swagger_enabled() is True
