"""
Pentrix / Lab Instances — provisioning abstraction.

This is the one integration point where ERPX would talk to real
infrastructure (Docker Engine API, Kubernetes, a cloud VM API, etc.) to
actually spin up an isolated environment per student. That integration
is deliberately left as a pluggable interface rather than a concrete
Docker/Kubernetes client: which backend to use is an infrastructure
decision for GIR Technologies to make (self-hosted Docker swarm vs. a
cloud provider vs. Kubernetes), and wiring up real credentials/endpoints
isn't something to hardcode into the application layer.

`StubProvisioner` below is a working, deterministic placeholder so the
rest of the module (status transitions, expiry, access control) is
fully functional and testable end-to-end today. Swapping in a real
provisioner later is a one-line change in `get_provisioner()` — nothing
else in this module needs to change, since everything else talks to the
`LabProvisioner` interface, never to Docker/Kubernetes directly.
"""

import secrets
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ProvisionedEnvironment:
    environment_ref: str
    access_endpoint: str


class LabProvisioner(ABC):
    @abstractmethod
    async def provision(self, lab_id: uuid.UUID, environment_image: str) -> ProvisionedEnvironment:
        """Start an isolated environment and return a handle to reach it."""

    @abstractmethod
    async def terminate(self, environment_ref: str) -> None:
        """Tear down a previously provisioned environment."""


class StubProvisioner(LabProvisioner):
    """
    Deterministic placeholder provisioner. Generates a fake container
    reference and access URL rather than calling real infrastructure.
    Replace with a DockerProvisioner / KubernetesProvisioner / cloud VM
    provisioner when GIR Technologies is ready to wire up real backends.
    """

    async def provision(self, lab_id: uuid.UUID, environment_image: str) -> ProvisionedEnvironment:
        environment_ref = f"stub-{secrets.token_hex(8)}"
        access_endpoint = f"https://labs.erpx.internal/{environment_ref}"
        return ProvisionedEnvironment(environment_ref=environment_ref, access_endpoint=access_endpoint)

    async def terminate(self, environment_ref: str) -> None:
        return None


def get_provisioner() -> LabProvisioner:
    return StubProvisioner()
