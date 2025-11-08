"""
Módulo principal do sistema de monitoramento.

Este módulo gerencia a inicialização e execução do sistema de monitoramento,
incluindo agendamento de tarefas, gerenciamento do ciclo de vida e shutdown graceful.
"""
import logging
import signal
import sys
import time
import traceback
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Callable, Optional

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobExecutionEvent
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from check import SiteChecker
from config import Settings, load_settings
from report import ReportGenerator
from utils import send_slack

# Configuração de logging
logger = logging.getLogger(__name__)

# Constantes
DEFAULT_SHUTDOWN_WAIT_TIME = 10  # Segundos para aguardar jobs terminarem
DEFAULT_MAIN_LOOP_SLEEP = 60  # Segundos entre iterações do loop principal
DEFAULT_INITIAL_JOB_DELAY = 10  # Segundos antes de executar jobs agendados
DEFAULT_THREAD_POOL_SIZE = 5  # Tamanho do thread pool para jobs


class MonitoringService:
    """
    Serviço principal de monitoramento.
    
    Gerencia o ciclo de vida completo do sistema de monitoramento, incluindo:
    - Inicialização de componentes
    - Configuração e execução do scheduler
    - Tratamento de sinais do sistema
    - Shutdown graceful
    """
    
    def __init__(self, settings: Settings):
        """
        Inicializa o serviço de monitoramento.
        
        Args:
            settings: Configurações do sistema.
            
        Raises:
            ValueError: Se as configurações forem inválidas.
        """
        self.settings = settings
        self.scheduler: Optional[BackgroundScheduler] = None
        self.checker: Optional[SiteChecker] = None
        self.report_gen: Optional[ReportGenerator] = None
        self._shutdown_requested = False
        self._setup_logging()
        logger.info("MonitoringService inicializado")
    
    def _setup_logging(self) -> None:
        """Configura logging básico se não estiver configurado."""
        if not logging.getLogger().handlers:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
    
    def _initialize_components(self) -> None:
        """
        Inicializa os componentes do sistema.
        
        Raises:
            RuntimeError: Se houver erro na inicialização dos componentes.
        """
        try:
            logger.info("Inicializando componentes...")
            self.checker = SiteChecker(self.settings)
            self.report_gen = ReportGenerator(self.settings)
            logger.info("Componentes inicializados com sucesso")
        except Exception as e:
            logger.error(f"Erro ao inicializar componentes: {e}", exc_info=True)
            raise RuntimeError(f"Falha na inicialização dos componentes: {e}") from e
    
    def _create_scheduler(self) -> BackgroundScheduler:
        """
        Cria e configura o scheduler.
        
        Returns:
            Instância configurada do BackgroundScheduler.
        """
        # Configura job stores e executors
        jobstores = {
            'default': MemoryJobStore()
        }
        executors = {
            'default': ThreadPoolExecutor(max_workers=DEFAULT_THREAD_POOL_SIZE)
        }
        job_defaults = {
            'coalesce': True,  # Executa apenas uma vez se múltiplas execuções estiverem atrasadas
            'max_instances': 1,  # Apenas uma instância de cada job por vez
            'misfire_grace_time': 30  # Tempo de tolerância para jobs atrasados
        }
        
        scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone=self.settings.tz
        )
        
        # Adiciona listeners para monitoramento
        scheduler.add_listener(
            self._on_job_executed,
            EVENT_JOB_EXECUTED
        )
        scheduler.add_listener(
            self._on_job_error,
            EVENT_JOB_ERROR
        )
        
        logger.info("Scheduler configurado com sucesso")
        return scheduler
    
    def _on_job_executed(self, event: JobExecutionEvent) -> None:
        """
        Callback chamado quando um job é executado com sucesso.
        
        Args:
            event: Evento de execução do job.
        """
        logger.debug(f"Job '{event.job_id}' executado com sucesso")
    
    def _on_job_error(self, event: JobExecutionEvent) -> None:
        """
        Callback chamado quando um job falha.
        
        Args:
            event: Evento de execução do job.
        """
        exception = event.exception
        job_id = event.job_id
        
        logger.error(
            f"Erro na execução do job '{job_id}': {exception}",
            exc_info=exception
        )
        
        # Tenta enviar notificação (sem bloquear se falhar)
        try:
            error_msg = (
                f"🚨 Erro crítico no job '{job_id}'\n"
                f"Exceção: {exception}\n"
                f"Traceback:\n{traceback.format_exception(type(exception), exception, exception.__traceback__)}"
            )
            send_slack(self.settings, error_msg)
        except Exception as e:
            logger.warning(f"Erro ao enviar notificação de falha do job: {e}")
    
    def _create_job_check(self) -> Callable[[], None]:
        """
        Cria a função de job de checagem periódica.
        
        Returns:
            Função do job de checagem.
        """
        def job_check():
            """Job de checagem periódica do site."""
            logger.info("Executando checagem periódica...")
            try:
                result = self.checker.perform_check()
                if result.get("ok_http") and result.get("ok_playwright"):
                    logger.info("Checagem concluída com sucesso")
                else:
                    logger.warning(
                        f"Checagem concluída com falhas: "
                        f"HTTP={result.get('ok_http')}, "
                        f"Playwright={result.get('ok_playwright')}"
                    )
            except Exception as e:
                logger.error(f"Erro crítico no job de checagem: {e}", exc_info=True)
                # Notificação já é enviada pelo listener de erros
                raise  # Re-raise para o scheduler lidar
        
        return job_check
    
    def _create_job_daily_report(self) -> Callable[[], None]:
        """
        Cria a função de job de relatório diário.
        
        Returns:
            Função do job de relatório diário.
        """
        def job_daily_report():
            """Job de geração de relatório diário."""
            logger.info("Executando geração de relatório diário...")
            try:
                today = datetime.now(self.settings.tz).date()
                report_path = self.report_gen.generate_daily_report(for_date=today)
                logger.info(f"Relatório diário gerado com sucesso: {report_path}")
            except Exception as e:
                logger.error(f"Erro ao gerar relatório diário: {e}", exc_info=True)
                raise  # Re-raise para o scheduler lidar
        
        return job_daily_report
    
    def _create_job_monthly_report(self) -> Callable[[], None]:
        """
        Cria a função de job de relatório mensal.
        
        Returns:
            Função do job de relatório mensal.
        """
        def job_monthly_report():
            """Job de geração de relatório mensal."""
            logger.info("Executando geração de relatório mensal...")
            try:
                report_path = self.report_gen.generate_monthly_report()
                logger.info(f"Relatório mensal gerado com sucesso: {report_path}")
            except Exception as e:
                logger.error(f"Erro ao gerar relatório mensal: {e}", exc_info=True)
                raise  # Re-raise para o scheduler lidar
        
        return job_monthly_report
    
    def _schedule_jobs(self) -> None:
        """Agenda todos os jobs no scheduler."""
        now = datetime.now(self.settings.tz)
        
        # Job de checagem periódica
        self.scheduler.add_job(
            func=self._create_job_check(),
            trigger='interval',
            minutes=self.settings.CHECK_INTERVAL_MINUTES,
            id='check_site',
            name='Checagem Periódica do Site',
            next_run_time=now,  # Executa imediatamente
            replace_existing=True
        )
        logger.info(
            f"Job de checagem agendado: intervalo de {self.settings.CHECK_INTERVAL_MINUTES} minutos"
        )
        
        # Job de relatório diário
        initial_delay = timedelta(seconds=DEFAULT_INITIAL_JOB_DELAY)
        self.scheduler.add_job(
            func=self._create_job_daily_report(),
            trigger='interval',
            days=1,
            id='daily_report',
            name='Relatório Diário',
            next_run_time=now + initial_delay,
            replace_existing=True
        )
        logger.info("Job de relatório diário agendado: intervalo de 1 dia")
        
        # Job de relatório mensal
        self.scheduler.add_job(
            func=self._create_job_monthly_report(),
            trigger='interval',
            days=30,
            id='monthly_report',
            name='Relatório Mensal',
            next_run_time=now + initial_delay,
            replace_existing=True
        )
        logger.info("Job de relatório mensal agendado: intervalo de 30 dias")
    
    def _setup_signal_handlers(self) -> None:
        """Configura handlers para sinais do sistema (SIGINT, SIGTERM)."""
        def signal_handler(signum, frame):
            """Handler para sinais de shutdown."""
            signal_name = signal.Signals(signum).name
            logger.info(f"Sinal {signal_name} recebido, iniciando shutdown graceful...")
            self.request_shutdown()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        logger.debug("Signal handlers configurados")
    
    def request_shutdown(self) -> None:
        """Solicita shutdown graceful do serviço."""
        self._shutdown_requested = True
        logger.info("Shutdown solicitado")
    
    def start(self) -> None:
        """
        Inicia o serviço de monitoramento.
        
        Raises:
            RuntimeError: Se houver erro ao iniciar o scheduler.
        """
        try:
            logger.info("Iniciando serviço de monitoramento...")
            
            # Inicializa componentes
            self._initialize_components()
            
            # Cria e configura scheduler
            self.scheduler = self._create_scheduler()
            
            # Agenda jobs
            self._schedule_jobs()
            
            # Configura signal handlers
            self._setup_signal_handlers()
            
            # Inicia scheduler
            self.scheduler.start()
            
            if not self.scheduler.running:
                raise RuntimeError("Falha ao iniciar scheduler")
            
            logger.info("Serviço de monitoramento iniciado com sucesso")
            logger.info(f"Scheduler rodando: {self.scheduler.running}")
            logger.info(f"Jobs agendados: {len(self.scheduler.get_jobs())}")
            
        except Exception as e:
            logger.error(f"Erro ao iniciar serviço: {e}", exc_info=True)
            self.shutdown()
            raise RuntimeError(f"Falha ao iniciar o serviço: {e}") from e
    
    def run(self) -> None:
        """
        Executa o loop principal do serviço.
        
        Este método bloqueia até que um shutdown seja solicitado.
        """
        if not self.scheduler or not self.scheduler.running:
            raise RuntimeError("Serviço não está iniciado. Chame start() primeiro.")
        
        logger.info("Entrando no loop principal...")
        
        try:
            while not self._shutdown_requested:
                time.sleep(DEFAULT_MAIN_LOOP_SLEEP)
                
                # Health check básico
                if not self.scheduler.running:
                    logger.error("Scheduler parou inesperadamente")
                    break
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt recebido")
            self.request_shutdown()
        except Exception as e:
            logger.error(f"Erro no loop principal: {e}", exc_info=True)
            self.request_shutdown()
        finally:
            self.shutdown()
    
    def shutdown(self, wait: bool = True) -> None:
        """
        Encerra o serviço de forma graceful.
        
        Args:
            wait: Se True, aguarda jobs terminarem antes de encerrar.
        """
        logger.info("Encerrando serviço de monitoramento...")
        
        if self.scheduler:
            try:
                if self.scheduler.running:
                    if wait:
                        logger.info(f"Aguardando até {DEFAULT_SHUTDOWN_WAIT_TIME}s para jobs terminarem...")
                        self.scheduler.shutdown(wait=True, timeout=DEFAULT_SHUTDOWN_WAIT_TIME)
                    else:
                        self.scheduler.shutdown(wait=False)
                    logger.info("Scheduler encerrado")
                else:
                    logger.debug("Scheduler já estava parado")
            except Exception as e:
                logger.error(f"Erro ao encerrar scheduler: {e}", exc_info=True)
        
        logger.info("Serviço encerrado")
    
    @contextmanager
    def lifecycle(self):
        """
        Context manager para gerenciar o ciclo de vida do serviço.
        
        Example:
            ```python
            with service.lifecycle():
                service.run()
            ```
        """
        try:
            self.start()
            yield self
        finally:
            self.shutdown()


def main() -> int:
    """
    Função principal de entrada do programa.
    
    Returns:
        Código de saída (0 para sucesso, não-zero para erro).
    """
    service: Optional[MonitoringService] = None
    
    try:
        # Carrega configurações
        logger.info("Carregando configurações...")
        settings = load_settings()
        logger.info("Configurações carregadas com sucesso")
        
        # Cria e inicia serviço
        service = MonitoringService(settings)
        
        with service.lifecycle():
            service.run()
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("Interrupção do usuário recebida")
        return 130  # Código padrão para SIGINT
    except Exception as e:
        logger.critical(f"Erro fatal: {e}", exc_info=True)
        
        # Tenta enviar notificação de erro fatal
        try:
            if service and service.settings:
                send_slack(
                    service.settings,
                    f"🚨 ERRO FATAL no sistema de monitoramento\n"
                    f"Erro: {e}\n"
                    f"Traceback:\n{traceback.format_exc()}"
                )
        except Exception as notify_error:
            logger.error(f"Erro ao enviar notificação de erro fatal: {notify_error}")
        
        return 1
    finally:
        if service:
            service.shutdown(wait=False)


if __name__ == "__main__":
    # Configura logging básico se executado diretamente
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    exit_code = main()
    sys.exit(exit_code)