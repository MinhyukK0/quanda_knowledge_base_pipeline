"""Kafka 브로커 설정"""

import ssl

from faststream.kafka import KafkaBroker
from faststream.security import SASLOAuthBearer

from src.conf.settings import settings


def _create_broker() -> KafkaBroker:
    """Kafka 브로커 생성"""
    if settings.kafka_use_iam:
        # MSK Serverless with IAM authentication
        from aiokafka.abc import AbstractTokenProvider
        from aws_msk_iam_sasl_signer import MSKAuthTokenProvider

        class MSKTokenProvider(AbstractTokenProvider):
            async def token(self):
                token, _ = MSKAuthTokenProvider.generate_auth_token(settings.aws_region)
                return token

        return KafkaBroker(
            settings.kafka_bootstrap_servers,
            security=SASLOAuthBearer(ssl_context=ssl.create_default_context()),
            sasl_oauth_token_provider=MSKTokenProvider(),
        )

    # Local development (PLAINTEXT)
    return KafkaBroker(settings.kafka_bootstrap_servers)


broker = _create_broker()
