document.addEventListener('DOMContentLoaded', () => {
    // Referencias a elementos del DOM
    const form = document.getElementById('prestamo-form');
    const inputNombre = document.getElementById('nombre');
    const inputIdentificacion = document.getElementById('identificacion');
    const userDatalist = document.getElementById('user-list');
    const inputArea = document.getElementById('area');
    const selectUbicacion = document.getElementById('ubicacion');
    const inputEdificio = document.getElementById('edificio');
    const selectPrestadoPor = document.getElementById('prestado_por');
    const registrosTbody = document.querySelector('#registros-table tbody');
    const btnLimpiar = document.getElementById('clear-form');
    const searchInput = document.getElementById('search-input');
    const pcCheckbox = document.getElementById('pc');
    const pcNumeroGroup = document.getElementById('pc-numero-group');
    const pcNumeroSelect = document.getElementById('pc_numero');
    const devolucionModal = document.getElementById('devolucion-modal');
    const modalRecibidoPor = document.getElementById('modal-recibido-por');
    const btnModalCancelar = document.getElementById('modal-btn-cancelar');
    const btnModalConfirmar = document.getElementById('modal-btn-confirmar');
    const btnModalClose = document.getElementById('modal-btn-close');

    let initialData = { usuarios: [], ubicaciones: [], auxiliares: [] };
    let equipmentData = [];
    let prestamoIdParaDevolver = null;

    // --- SEGURIDAD: Obtener el token CSRF de la meta etiqueta ---
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

    // --- FUNCIONES ---
    async function cargarDatosIniciales() {
        try {
            const [initialResponse, equiposResponse] = await Promise.all([
                fetch('/api/initial-data'),
                fetch('/api/equipos')
            ]);
            if (!initialResponse.ok || !equiposResponse.ok) throw new Error('Error de red al cargar datos.');

            initialData = await initialResponse.json();
            equipmentData = await equiposResponse.json();

            // Poblar datalist de usuarios
            userDatalist.innerHTML = '';
            initialData.usuarios.forEach(u => {
                const option = document.createElement('option');
                option.value = u.nombre;
                userDatalist.appendChild(option);
            });

            // Poblar select de ubicaciones
            selectUbicacion.innerHTML = '<option value="">Seleccione...</option>';
            initialData.ubicaciones.forEach(u => {
                const option = document.createElement('option');
                option.value = u.nombre;
                option.textContent = u.nombre;
                option.dataset.edificio = u.edificio;
                selectUbicacion.appendChild(option);
            });

            // Poblar select de equipos (PC)
            pcNumeroSelect.innerHTML = '<option value="">Nº</option>';
            equipmentData.forEach(eq => {
                pcNumeroSelect.innerHTML += `<option value="${eq.id}">${eq.id}</option>`;
            });

            // Función para poblar selects de auxiliares
            const poblarSelectAuxiliares = (selectElement) => {
                selectElement.innerHTML = '<option value="">Seleccione...</option>';
                initialData.auxiliares.forEach(a => {
                    const option = document.createElement('option');
                    option.value = a.nombre;
                    option.textContent = a.nombre;
                    selectElement.appendChild(option);
                });
            };
            poblarSelectAuxiliares(selectPrestadoPor);
            poblarSelectAuxiliares(modalRecibidoPor);

        } catch (error) {
            console.error('Error al cargar datos iniciales:', error);
            alert('No se pudieron cargar los datos para los formularios.');
        }
    }

    async function cargarRegistros() {
        try {
            const response = await fetch('/api/prestamos');
            if (!response.ok) throw new Error('Error al obtener los préstamos');
            const prestamos = await response.json();
            renderTabla(prestamos);
        } catch (error) {
            console.error('Error al cargar registros:', error);
        }
    }
    
    // *** FUNCIÓN SEGURA PARA RENDERIZAR LA TABLA (Anti-XSS) ***
    function renderTabla(prestamos) {
        registrosTbody.innerHTML = ''; // Limpiar tabla
        if (prestamos.length === 0) {
            const tr = registrosTbody.insertRow();
            const td = tr.insertCell();
            td.colSpan = 7;
            td.textContent = 'No hay préstamos pendientes.';
            td.style.textAlign = 'center';
            return;
        }

        prestamos.forEach(p => {
            const tr = registrosTbody.insertRow();
            
            // Crear celdas de forma segura
            const ubicacionInfo = p.pc && p.pc_numero ? `${p.ubicacion} (PC: ${p.pc_numero})` : p.ubicacion;

            tr.insertCell().textContent = p.id;
            tr.insertCell().textContent = p.fecha;
            tr.insertCell().textContent = p.nombre;
            tr.insertCell().textContent = ubicacionInfo;
            tr.insertCell().textContent = p.hora_inicio;

            // Celda de estado
            const statusCell = tr.insertCell();
            const statusSpan = document.createElement('span');
            statusSpan.className = 'status-pendiente';
            statusSpan.textContent = 'Pendiente';
            statusCell.appendChild(statusSpan);

            // Celda de acciones
            const actionCell = tr.insertCell();
            const devolverBtn = document.createElement('button');
            devolverBtn.className = 'btn-devolver';
            devolverBtn.textContent = 'Devolver';
            devolverBtn.dataset.id = p.id;
            actionCell.appendChild(devolverBtn);
        });
    }

    function limpiarFormulario() {
        form.reset();
        document.getElementById('fecha').valueAsDate = new Date();
        const now = new Date();
        document.getElementById('hora_inicio').value = now.toTimeString().slice(0, 5);
        inputIdentificacion.value = '';
        inputArea.value = '';
        inputEdificio.value = '';
        pcNumeroGroup.classList.add('hidden');
    }

    // --- EVENT LISTENERS ---
    inputNombre.addEventListener('input', () => {
        const usuario = initialData.usuarios.find(u => u.nombre === inputNombre.value);
        inputIdentificacion.value = usuario ? usuario.id : '';
        inputArea.value = usuario ? usuario.area : '';
    });

    selectUbicacion.addEventListener('change', () => {
        const selectedOption = selectUbicacion.options[selectUbicacion.selectedIndex];
        inputEdificio.value = selectedOption ? (selectedOption.dataset.edificio || '') : '';
    });

    pcCheckbox.addEventListener('change', () => {
        pcNumeroGroup.classList.toggle('hidden', !pcCheckbox.checked);
        if (!pcCheckbox.checked) {
            pcNumeroSelect.value = '';
        }
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (inputNombre.value && !inputIdentificacion.value) {
            alert('El nombre ingresado no está en la lista. Por favor, seleccione un nombre válido.');
            inputNombre.focus();
            return;
        }

        let pcPertenece = null;
        if (pcCheckbox.checked && pcNumeroSelect.value) {
            const selectedId = parseInt(pcNumeroSelect.value, 10);
            const equipo = equipmentData.find(eq => eq.id === selectedId);
            if (equipo) pcPertenece = equipo.pertenece;
        }

        const formData = {
            fecha: document.getElementById('fecha').value,
            identificacion: inputIdentificacion.value,
            nombre: inputNombre.value,
            area: inputArea.value,
            ubicacion: selectUbicacion.value,
            edificio: inputEdificio.value,
            hora_inicio: document.getElementById('hora_inicio').value,
            prestado_por: selectPrestadoPor.value,
            observaciones: document.getElementById('observaciones').value,
            pc: pcCheckbox.checked,
            pc_numero: pcCheckbox.checked ? pcNumeroSelect.value : null,
            pc_pertenece: pcPertenece,
            kit: document.getElementById('kit').checked,
            aire: document.getElementById('aire').checked,
            cabinas: document.getElementById('cabinas').checked,
            consola: document.getElementById('consola').checked,
            vbeam: document.getElementById('vbeam').checked
        };

        if (formData.pc && !formData.pc_numero) {
            alert('Si selecciona PC, debe especificar el número.');
            pcNumeroSelect.focus();
            return;
        }

        try {
            const response = await fetch('/api/prestamos', { 
                method: 'POST', 
                headers: { 
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken // *** SEGURIDAD: Enviar token CSRF ***
                }, 
                body: JSON.stringify(formData) 
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || 'Error desconocido');
            alert(result.success);
            limpiarFormulario();
            cargarRegistros();
        } catch (error) {
            console.error('Error al guardar el préstamo:', error);
            alert(`Error: ${error.message}`);
        }
    });

    searchInput.addEventListener('keyup', () => {
        const searchTerm = searchInput.value.toLowerCase();
        registrosTbody.querySelectorAll('tr').forEach(row => {
            const rowText = row.textContent.toLowerCase();
            row.style.display = rowText.includes(searchTerm) ? '' : 'none';
        });
    });

    // --- Lógica del Modal ---
    registrosTbody.addEventListener('click', (e) => {
        if (e.target.classList.contains('btn-devolver')) {
            prestamoIdParaDevolver = e.target.dataset.id;
            modalRecibidoPor.value = '';
            devolucionModal.classList.remove('hidden');
        }
    });
    
    const closeModal = () => {
        devolucionModal.classList.add('hidden');
        prestamoIdParaDevolver = null;
    };
    
    btnModalCancelar.addEventListener('click', closeModal);
    btnModalClose.addEventListener('click', closeModal);

    btnModalConfirmar.addEventListener('click', async () => {
        const recibidoPor = modalRecibidoPor.value;
        if (!recibidoPor) {
            alert('Por favor, seleccione quién recibe el equipo.');
            return;
        }
        try {
            const response = await fetch(`/api/prestamos/${prestamoIdParaDevolver}/devolver`, { 
                method: 'POST', 
                headers: { 
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken // *** SEGURIDAD: Enviar token CSRF ***
                }, 
                body: JSON.stringify({ recibido_por: recibidoPor }) 
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error);
            alert(result.success);
            closeModal();
            cargarRegistros();
        } catch (error) {
            console.error('Error al registrar devolución:', error);
            alert(`Error: ${error.message}`);
        }
    });

    btnLimpiar.addEventListener('click', limpiarFormulario);

    // --- INICIALIZACIÓN ---
    async function inicializarApp() {
        await cargarDatosIniciales();
        await cargarRegistros();
        limpiarFormulario();
    }
    inicializarApp();
});
