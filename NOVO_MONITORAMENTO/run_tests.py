#!/usr/bin/env python
"""
Script auxiliar para executar testes do sistema de monitoramento.

Este script facilita a execução de testes com diferentes opções e configurações.
"""
import sys
import subprocess
from pathlib import Path


def run_tests(
    verbose: bool = False,
    coverage: bool = False,
    specific_test: str = None,
    markers: str = None
) -> int:
    """
    Executa os testes do projeto.
    
    Args:
        verbose: Se True, executa com verbosidade máxima.
        coverage: Se True, gera relatório de cobertura.
        specific_test: Caminho para teste específico (opcional).
        markers: Marcadores de teste para filtrar (opcional).
    
    Returns:
        Código de saída do pytest.
    """
    cmd = ["python", "-m", "pytest"]
    
    if verbose:
        cmd.append("-vv")
    else:
        cmd.append("-v")
    
    if coverage:
        cmd.extend(["--cov=.", "--cov-report=html", "--cov-report=term-missing"])
    
    if markers:
        cmd.extend(["-m", markers])
    
    if specific_test:
        cmd.append(specific_test)
    else:
        cmd.append("tests/")
    
    print(f"Executando: {' '.join(cmd)}")
    print("-" * 60)
    
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    return result.returncode


def main():
    """Função principal."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Executa testes automatizados do sistema de monitoramento.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Executa todos os testes
  python run_tests.py
  
  # Executa com cobertura
  python run_tests.py --coverage
  
  # Executa teste específico
  python run_tests.py tests/test_config.py
  
  # Executa testes marcados
  python run_tests.py --markers "unit"
  
  # Executa com verbosidade máxima
  python run_tests.py --verbose
        """
    )
    
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Gera relatório de cobertura de código"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Executa com verbosidade máxima"
    )
    
    parser.add_argument(
        "--test",
        "-t",
        type=str,
        help="Caminho para teste específico"
    )
    
    parser.add_argument(
        "--markers",
        "-m",
        type=str,
        help="Marcadores de teste para filtrar (ex: 'unit', 'ssl')"
    )
    
    args = parser.parse_args()
    
    exit_code = run_tests(
        verbose=args.verbose,
        coverage=args.coverage,
        specific_test=args.test,
        markers=args.markers
    )
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

