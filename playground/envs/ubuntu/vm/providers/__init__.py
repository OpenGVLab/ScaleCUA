from envs.ubuntu.vm.providers.base import VMManager, Provider


def create_vm_manager_and_provider(provider_name: str, region: str, **kwargs):
    """
    Factory function to get the Virtual Machine Manager and Provider instances based on the provided provider name.
    """
    provider_name = provider_name.lower().strip()
    if provider_name == "docker":
        from envs.ubuntu.vm.providers.docker.manager import DockerVMManager
        from envs.ubuntu.vm.providers.docker.provider import DockerProvider
        return DockerVMManager(), DockerProvider(region, **kwargs)
    else:
        raise NotImplementedError(f"{provider_name} not implemented!")
