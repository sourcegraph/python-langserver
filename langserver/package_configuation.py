import toml

class ConfigParser:
    def __init__(self, config_contents):
        self.parsed_config = {
            "source": [],
            "packages": {},
            "dev-packages": {},
        }
        
        self.parsed_config.update(toml.loads(config_contents))       
    
    @property
    def packages(self):
        """A dict of packages (keyed by the package's name) that 
        were specified by the configuration"""
        packages_by_name = {}

        for package_group in ["packages", "dev-packages"]:
            for package_name, version_info in self.parsed_config[package_group].items():
                if isinstance(version_info, str):
                    # e.g. version_info == ">= 1.0"
                    package = Package(package_name, version_info, DEFAULT_SOURCE.name)
                else:
                      # e.g. version_info == {'version': '*', 'index': 'custom_index'}
                    package = Package(package_name, version_info["version"], version_info["index"])

                packages_by_name[package.name] = package
            
        return packages_by_name

    @property
    def sources(self):
        """A dict of indices (keyed by the index's name) that 
        were specified by the configuration"""
        sources_by_name = {}
        for raw_source in self.parsed_config["source"]:
            source = Source(raw_source["name"], raw_source["url"], raw_source["verify_ssl"])
            sources_by_name[source.name] = source
        return sources_by_name

    def get_package_source(self, package):
        """Find the associated index to use for the given package"""
        return self.sources.get(package.index_name, DEFAULT_SOURCE)

class Package:
    def __init__(self, name, version, index_name):
        self.name = name
        self.version = version
        self.index_name = index_name

class Source:
    def __init__(self, name, url, verify_ssl):
        self.name = name
        self.url = url
        self.verify_ssl = verify_ssl

DEFAULT_SOURCE = Source("pypi", "https://pypi.python.org/simple", True)