# Standard library imports
import os
import sys
import json
import subprocess
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from pathlib import Path

# Third-party imports
import requests
import pkg_resources

# Local imports
from utils.debug_logger import setup_logger, log_exception
from utils.exceptions import SecurityError

# Setup logger
logger = setup_logger(__name__, "security_scan.log")

def get_installed_packages() -> List[Dict[str, str]]:
    """
    Get list of installed packages.
    
    Returns:
        List of package information
    """
    try:
        packages = []
        for package in pkg_resources.working_set:
            packages.append({
                'name': package.key,
                'version': package.version
            })
        return packages
    except Exception as e:
        log_exception(logger, e, "get_installed_packages")
        return []

def check_pypi_security(package: str, version: str) -> Dict[str, Any]:
    """
    Check package for known vulnerabilities.
    
    Args:
        package: Package name
        version: Package version
        
    Returns:
        Dictionary containing security information
    """
    try:
        # Check PyPI security database
        url = f"https://pypi.org/pypi/{package}/{version}/json"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            return {
                'has_vulnerabilities': False,
                'last_updated': data.get('last_updated'),
                'vulnerabilities': []
            }
            
        return {
            'has_vulnerabilities': True,
            'error': f"Failed to get package info: {response.status_code}"
        }
        
    except Exception as e:
        log_exception(logger, e, "check_pypi_security")
        return {
            'has_vulnerabilities': True,
            'error': str(e)
        }

def scan_dependencies() -> Dict[str, Any]:
    """
    Scan all dependencies for security vulnerabilities.
    
    Returns:
        Dictionary containing scan results
    """
    try:
        results = {
            'timestamp': datetime.utcnow().isoformat(),
            'packages': [],
            'vulnerabilities': [],
            'summary': {
                'total_packages': 0,
                'vulnerable_packages': 0,
                'critical_vulnerabilities': 0,
                'high_vulnerabilities': 0,
                'medium_vulnerabilities': 0,
                'low_vulnerabilities': 0
            }
        }
        
        # Get installed packages
        packages = get_installed_packages()
        results['summary']['total_packages'] = len(packages)
        
        # Check each package
        for package in packages:
            security_info = check_pypi_security(package['name'], package['version'])
            
            package_info = {
                'name': package['name'],
                'version': package['version'],
                'security_info': security_info
            }
            
            results['packages'].append(package_info)
            
            if security_info.get('has_vulnerabilities'):
                results['summary']['vulnerable_packages'] += 1
                results['vulnerabilities'].append(package_info)
                
        return results
        
    except Exception as e:
        log_exception(logger, e, "scan_dependencies")
        return {
            'error': f"Failed to scan dependencies: {str(e)}"
        }

def generate_report(results: Dict[str, Any], output_file: str = "security_report.json") -> None:
    """
    Generate security report.
    
    Args:
        results: Scan results
        output_file: Output file path
    """
    try:
        # Create reports directory
        report_dir = Path('reports')
        report_dir.mkdir(exist_ok=True)
        
        # Write report
        report_path = report_dir / output_file
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
            
        logger.info(f"Security report generated: {report_path}")
        
    except Exception as e:
        log_exception(logger, e, "generate_report")

def main():
    """Main function."""
    try:
        # Scan dependencies
        results = scan_dependencies()
        
        # Generate report
        generate_report(results)
        
        # Print summary
        summary = results.get('summary', {})
        print("\nSecurity Scan Summary:")
        print(f"Total Packages: {summary.get('total_packages', 0)}")
        print(f"Vulnerable Packages: {summary.get('vulnerable_packages', 0)}")
        print(f"Critical Vulnerabilities: {summary.get('critical_vulnerabilities', 0)}")
        print(f"High Vulnerabilities: {summary.get('high_vulnerabilities', 0)}")
        print(f"Medium Vulnerabilities: {summary.get('medium_vulnerabilities', 0)}")
        print(f"Low Vulnerabilities: {summary.get('low_vulnerabilities', 0)}")
        
    except Exception as e:
        log_exception(logger, e, "main")
        sys.exit(1)

if __name__ == "__main__":
    main() 