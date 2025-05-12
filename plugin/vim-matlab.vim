" Vim-Matlab Plugin con Soporte para Celdas
" Este plugin proporciona funcionalidad completa para interactuar con Matlab desde Vim

" Prevent loading the plugin multiple times
if exists("g:loaded_vim_matlab")
    finish
endif
let g:loaded_vim_matlab = 1

" Default settings
if !exists('g:matlab_server_split')
    let g:matlab_server_split = 'vertical'
endif

" Performance optimization - disable Python's GC during operaciones
if !exists('g:matlab_optimize_performance')
    let g:matlab_optimize_performance = 1
endif

" Set up Matlab file type detection
augroup vim_matlab
    autocmd!
    autocmd BufNewFile,BufRead *.m set filetype=matlab
augroup END

" Server commands
let s:server_script = expand('<sfile>:p:h') . '/matlab_server.py'
let s:controller_script = expand('<sfile>:p:h') . '/matlab_cli_controller.py'

" Define the split command based on user preference
if g:matlab_server_split ==? 'horizontal'
    let s:split_command = ':split term://'
else
    let s:split_command = ':vsplit term://'
endif

" Python imports for controller use
let s:plugin_path = expand('<sfile>:p:h')
execute 'py3 import sys'
execute 'py3 sys.path.append("' . s:plugin_path . '")'
execute 'py3 import matlab_cli_controller'

" Optionally set up performance optimizations
if g:matlab_optimize_performance
    python3 << EOF
import gc
# Disable GC during operaciones críticas
gc_state = gc.isenabled()
EOF
endif

" Command to launch the Matlab server
command! MatlabLaunchServer :execute 'normal! ' . s:split_command . 'python3 ' . s:server_script . '<CR>'

" Create cell commands
command! MatlabNormalModeCreateCell :execute 'normal! :set paste<CR>m`O%%<ESC>``:set nopaste<CR>'
command! MatlabVisualModeCreateCell :execute 'normal! gvD:set paste<CR>O%%<CR>%%<ESC>P:set nopaste<CR>'
command! MatlabInsertModeCreateCell :execute 'normal! I%% '

" Default key mappings
if !exists('g:matlab_auto_mappings')
    let g:matlab_auto_mappings = 1
endif

" Functions to interact with Matlab via Python controller
function! s:InitController()
    if !exists('s:controller_initialized')
        py3 << EOF
import matlab_cli_controller
controller = None
try:
    controller = matlab_cli_controller.MatlabCliController()
    print("Matlab controller initialized")
except Exception as e:
    print(f"Error initializing Matlab controller: {e}")
EOF
        let s:controller_initialized = 1
    endif
endfunction

function! s:RunMatlabCode(code)
    call s:InitController()
    py3 << EOF
try:
    if 'gc_state' in globals():
        gc.disable()  # Disable GC during operación crítica
        
    if controller is not None:
        code = vim.eval('a:code')
        controller.run_code(code)
    else:
        print("Matlab controller not initialized. Run :MatlabLaunchServer first.")
        
    if 'gc_state' in globals() and gc_state:
        gc.enable()  # Re-enable GC if estaba enabled
except Exception as e:
    print(f"Error running Matlab code: {e}")
    if 'gc_state' in globals() and gc_state:
        gc.enable()  # Re-enable GC if estaba enabled
EOF
endfunction

function! s:RunCurrentFile()
    call s:InitController()
    py3 << EOF
try:
    if 'gc_state' in globals():
        gc.disable()  # Disable GC during operación crítica
        
    if controller is not None:
        filepath = vim.eval('expand("%:p")')
        controller.run_file(filepath)
    else:
        print("Matlab controller not initialized. Run :MatlabLaunchServer first.")
        
    if 'gc_state' in globals() and gc_state:
        gc.enable()  # Re-enable GC if estaba enabled
except Exception as e:
    print(f"Error running current file in Matlab: {e}")
    if 'gc_state' in globals() and gc_state:
        gc.enable()  # Re-enable GC if estaba enabled
EOF
endfunction

function! s:RunCurrentSelection() range
    let l:selection = getline(a:firstline, a:lastline)
    let l:code = join(l:selection, '; ')
    call s:RunMatlabCode(l:code)
endfunction

" Función para buscar celdas en archivos MATLAB
function! s:GetCurrentCell()
    " Obtener la posición actual
    let l:current_line = line('.')
    let l:cell_start = l:current_line
    let l:cell_end = l:current_line
    
    " Buscar hacia atrás para encontrar el inicio de la celda
    while l:cell_start > 1
        let l:cell_start -= 1
        let l:line_content = getline(l:cell_start)
        if l:line_content =~# '^\s*%%'
            break
        endif
    endwhile
    
    " Si no se encontró el inicio de la celda, usar la línea actual
    if l:cell_start == 1 && getline(l:cell_start) !~# '^\s*%%'
        let l:cell_start = l:current_line
    endif
    
    " Buscar hacia adelante para encontrar el final de la celda
    let l:last_line = line('$')
    while l:cell_end < l:last_line
        let l:cell_end += 1
        let l:line_content = getline(l:cell_end)
        if l:line_content =~# '^\s*%%'
            let l:cell_end -= 1
            break
        endif
    endwhile
    
    " Obtener el contenido de la celda
    let l:cell_content = getline(l:cell_start, l:cell_end)
    return l:cell_content
endfunction

" Función para ejecutar la celda actual
function! s:RunCurrentCell()
    let l:cell_content = s:GetCurrentCell()
    if len(l:cell_content) == 0
        echo "No cell content found"
        return
    endif
    
    call s:InitController()
    
    " Unir el contenido de la celda
    let l:code = join(l:cell_content, "\n")
    
    py3 << EOF
try:
    if 'gc_state' in globals():
        gc.disable()  # Disable GC during operación crítica
        
    if controller is not None:
        cell_code = vim.eval('l:code')
        controller.run_cell(cell_code)
    else:
        print("Matlab controller not initialized. Run :MatlabLaunchServer first.")
        
    if 'gc_state' in globals() and gc_state:
        gc.enable()  # Re-enable GC if estaba enabled
except Exception as e:
    print(f"Error running current cell in Matlab: {e}")
    if 'gc_state' in globals() and gc_state:
        gc.enable()  # Re-enable GC if estaba enabled
EOF
endfunction

" Función para mover a la siguiente celda
function! s:NextCell()
    let l:current_line = line('.')
    let l:last_line = line('$')
    
    " Buscar la siguiente celda
    let l:next_cell = l:current_line + 1
    while l:next_cell <= l:last_line
        if getline(l:next_cell) =~# '^\s*%%'
            " Encontrada la siguiente celda
            execute l:next_cell
            return
        endif
        let l:next_cell += 1
    endwhile
    
    " Si no se encuentra ninguna celda, ir al final del archivo
    execute l:last_line
endfunction

" Función para mover a la celda anterior
function! s:PreviousCell()
    let l:current_line = line('.')
    
    " Buscar la celda anterior
    let l:prev_cell = l:current_line - 1
    while l:prev_cell >= 1
        if getline(l:prev_cell) =~# '^\s*%%'
            " Encontrada la celda anterior
            execute l:prev_cell
            return
        endif
        let l:prev_cell -= 1
    endwhile
    
    " Si no se encuentra ninguna celda, ir al principio del archivo
    execute 1
endfunction

" Función para enviar Ctrl+C a Matlab
function! s:SendCtrlC()
    call s:InitController()
    py3 << EOF
try:
    if controller is not None:
        controller.send_ctrl_c()
    else:
        print("Matlab controller not initialized. Run :MatlabLaunchServer first.")
except Exception as e:
    print(f"Error sending Ctrl+C to Matlab: {e}")
EOF
endfunction

" Create the commands
command! -nargs=1 MatlabRunCode call s:RunMatlabCode(<args>)
command! MatlabRunFile call s:RunCurrentFile()
command! -range MatlabRunSelection <line1>,<line2>call s:RunCurrentSelection()
command! MatlabRunCell call s:RunCurrentCell()
command! MatlabNextCell call s:NextCell()
command! MatlabPreviousCell call s:PreviousCell()
command! MatlabCancel call s:SendCtrlC()

" Create the key mappings
if g:matlab_auto_mappings
    augroup matlab_mappings
        autocmd!
        " Cell creation mappings
        autocmd FileType matlab nnoremap <buffer><silent> <C-l> :MatlabNormalModeCreateCell<CR>
        autocmd FileType matlab vnoremap <buffer><silent> <C-l> :<C-u>MatlabVisualModeCreateCell<CR>
        autocmd FileType matlab inoremap <buffer><silent> <C-l> <C-o>:MatlabInsertModeCreateCell<CR>
        
        " Run code mappings
        autocmd FileType matlab nnoremap <buffer><silent> <F5> :MatlabRunFile<CR>
        autocmd FileType matlab vnoremap <buffer><silent> <F9> :<C-u>MatlabRunSelection<CR>
        
        " Cell navigation and running
