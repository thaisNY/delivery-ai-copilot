"""Camada de fonte de dados.

Hoje a demo lê dados sintéticos do Postgres. Os campos de merchants / orders / reviews foram
pensados para espelhar o que a API de parceiros do iFood (Merchant API) entrega a um restaurante
integrado, então ir para produção significa implementar `MerchantApiSource`
e sincronizar para as mesmas tabelas. As ferramentas do agente não mudam.

Acesso à API oficial exige conta no Portal do Desenvolvedor (com CNPJ), homologação do app e
autorização de cada loja, por isso não está implementado aqui.
"""
from abc import ABC, abstractmethod


class DataSource(ABC):
    @abstractmethod
    def merchants(self) -> list[dict]: ...

    @abstractmethod
    def orders(self, merchant_id: str, since) -> list[dict]: ...

    @abstractmethod
    def reviews(self, merchant_id: str, since) -> list[dict]: ...


class SyntheticSource(DataSource):
    """Lê do gerador sintético (usado pelo pipeline)."""

    def __init__(self):
        from pipeline.generate import generate
        self._m, _, self._o, self._r = generate()

    def merchants(self):
        return self._m

    def orders(self, merchant_id, since):
        return [o for o in self._o if o["merchant_id"] == merchant_id and o["created_at"] >= since]

    def reviews(self, merchant_id, since):
        return [r for r in self._r if r["merchant_id"] == merchant_id and r["created_at"] >= since]


class MerchantApiSource(DataSource):
    """Ponto de extensão para a API oficial, usando o token OAuth do restaurante autorizado."""

    def __init__(self, access_token: str):
        self.token = access_token

    def merchants(self):
        raise NotImplementedError("Requer credenciais homologadas no Portal do Desenvolvedor iFood")

    def orders(self, merchant_id, since):
        raise NotImplementedError

    def reviews(self, merchant_id, since):
        raise NotImplementedError
