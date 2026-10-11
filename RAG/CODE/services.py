"""Assemblage des composants (injection de dépendances simple).

Un seul point de construction des objets partagés : client Neo4j, référentiel, extracteurs,
encodeur, pipeline d'ingestion, moteur de recherche et workflow LangGraph. L'API, les
scripts et les évaluations utilisent tous ce module, ce qui garantit une configuration
identique partout.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

from core.llm import LLMClient, build_llm
from core.settings import CODE_DIR, Settings, get_settings
from extraction.linker import EntityLinker
from extraction.llm_extractor import LLMExtractor
from extraction.referential import Referential, load_referential
from extraction.rules import RuleExtractor
from ingestion.pipeline import IngestionPipeline
from ingestion.processor import DocumentProcessor
from knowledge_graph.client import Neo4jClient
from knowledge_graph.repository import GraphRepository
from expert_discovery.service import ExpertService
from orchestration.sufficiency import TermStatistics
from orchestration.workflow import QAWorkflow
from recommendations.service import RecommendationService
from retrieval.access import AccessResolver
from retrieval.embeddings import Embedder, get_embedder
from retrieval.graph import GraphRetriever
from retrieval.retriever import Retriever
from retrieval.text_search import TextSearch


@dataclass
class Services:
    settings: Settings

    @cached_property
    def referential(self) -> Referential:
        return load_referential(self.settings.referentials_file)

    @cached_property
    def client(self) -> Neo4jClient:
        return Neo4jClient.from_settings(self.settings)

    @cached_property
    def repository(self) -> GraphRepository:
        return GraphRepository(self.client, self.referential)

    @cached_property
    def linker(self) -> EntityLinker:
        return EntityLinker(self.referential)

    @cached_property
    def llm(self) -> LLMClient:
        return build_llm(self.settings)

    @cached_property
    def embedder(self) -> Embedder:
        return get_embedder(self.settings.embedding_provider)

    @cached_property
    def processor(self) -> DocumentProcessor:
        rules = RuleExtractor(self.referential, CODE_DIR / "config" / "extraction_rules.yaml")
        llm_extractor = LLMExtractor(self.llm, self.referential) if self.settings.llm_enabled else None
        return DocumentProcessor(self.settings, self.referential, self.linker, rules, llm_extractor)

    @cached_property
    def pipeline(self) -> IngestionPipeline:
        return IngestionPipeline(self.settings, self.repository, self.processor, self.embedder)

    @cached_property
    def access(self) -> AccessResolver:
        return AccessResolver(self.client)

    @cached_property
    def graph_retriever(self) -> GraphRetriever:
        return GraphRetriever(self.client, self.linker, max_hops=self.settings.graph_max_hops)

    @cached_property
    def retriever(self) -> Retriever:
        return Retriever(self.client, TextSearch(self.client, self.embedder), self.graph_retriever,
                         rrf_k=self.settings.rrf_k, candidate_pool=self.settings.candidate_pool)

    @cached_property
    def experts(self) -> ExpertService:
        return ExpertService(self.client, self.linker, self.settings.reference_date)

    @cached_property
    def recommendations(self) -> RecommendationService:
        return RecommendationService(self.client, self.linker, self.embedder)

    @cached_property
    def term_stats(self) -> TermStatistics:
        rows = self.client.read("MATCH (c:Chunk) RETURN c.search_text AS text")
        return TermStatistics([r["text"] for r in rows])

    @cached_property
    def workflow(self) -> QAWorkflow:
        return QAWorkflow(self.settings, self.client, self.retriever, self.access, self.experts, self.referential,
                          self.llm, self.term_stats)

    def refresh_after_ingestion(self) -> None:
        """À appeler après une ingestion : statistiques lexicales et droits recalculés."""
        for name in ("term_stats", "workflow"):
            self.__dict__.pop(name, None)
        self.access.invalidate()

    def ensure_schema(self) -> None:
        self.repository.ensure_schema(self.embedder.dim)

    def close(self) -> None:
        if "client" in self.__dict__:
            self.client.close()


def build_services(settings: Settings | None = None) -> Services:
    return Services(settings or get_settings())
