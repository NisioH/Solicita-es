document.addEventListener('DOMContentLoaded', function () {
    // 1. Modal de Exportação Excel
    const btnExportar = document.getElementById('btnExportar');
    if (btnExportar) {
        btnExportar.addEventListener('click', function(e) {
            e.preventDefault();
            var myModal = new bootstrap.Modal(document.getElementById('modalExcel'));
            myModal.show();
        });
    }

    // 2. Modal de Detalhes
    const modalDetalhes = document.getElementById('modalDetalhes');
    if (modalDetalhes) {
        modalDetalhes.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            const fields = ['numero', 'safra', 'solicitante', 'centro', 'data', 'descricao', 'fornecedor', 'nota'];
            
            fields.forEach(field => {
                const val = button.getAttribute('data-' + field) || '-';
                const el = document.getElementById('modal-' + field);
                if (el) el.textContent = (val === 'None' || !val) ? '-' : val;
            });

            // Tratamento especial para Data de Recebimento
            let dataRec = button.getAttribute('data-data-recebido');
            if (dataRec && dataRec.includes('-')) {
                const p = dataRec.substring(0, 10).split('-');
                dataRec = `${p[2]}/${p[1]}/${p[0]}`;
            }
            document.getElementById('modal-data-recebido').textContent = dataRec || '-';

            // Status Badge
            const status = button.getAttribute('data-status') || '-';
            const statusEl = document.getElementById('modal-status');
            statusEl.textContent = status.toUpperCase();
            const s = status.toLowerCase();
            statusEl.className = 'badge rounded-pill fs-6 bg-' + 
                ((s === 'concluído' || s === 'recebido') ? 'success' : 
                 (s === 'reprovada' ? 'danger' : 
                 (s.includes('cancel') ? 'secondary' : 'info text-dark')));
        });
    }
});