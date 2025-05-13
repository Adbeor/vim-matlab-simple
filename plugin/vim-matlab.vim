" Corrected Vim-Matlab Plugin
" This plugin provides functionality to interact with Matlab from Vim

" Prevent loading the plugin multiple times
if exists("g:loaded_vim_matlab")
    finish
endif
let g:loaded_vim_matlab = 1

" Default settings
if !exists('g:matlab_server_split')
    let g:matlab_server_split = 'vertical'
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
    if controller is not None:
        code = vim.eval('a:code')
        controller.run_code([code])
    else:
        print("Matlab controller not initialized. Run :MatlabLaunchServer first.")
except Exception as e:
    print(f"Error running Matlab code: {e}")
EOF
endfunction

function! s:RunCurrentFile()
    call s:InitController()
    py3 << EOF
try:
    if controller is not None:
        filepath = vim.eval('expand("%:p")')
        controller.run_file(filepath)
        print(f"Running file: {filepath}")
    else:
        print("Matlab controller not initialized. Run :MatlabLaunchServer first.")
except Exception as e:
    print(f"Error running current file in Matlab: {e}")
EOF
endfunction

function! s:RunCurrentSelection() range
    let l:selection = getline(a:firstline, a:lastline)
    let l:code = join(l:selection, '; ')
    call s:RunMatlabCode(l:code)
endfunction

" NUEVA FUNCIÓN: Ejecutar la celda actual de Matlab
function! s:RunCurrentCell()
    call s:InitController()
    
    " Encuentra los límites de la celda actual
    let current_line = line('.')
    let cell_start = current_line
    let cell_end = current_line
    
    " Buscar hacia atrás para encontrar el inicio de la celda
    while cell_start > 1 && getline(cell_start - 1) !~ '^\s*%%'
        let cell_start -= 1
    endwhile
    
    " Buscar hacia adelante para encontrar el final de la celda
    while cell_end < line('$') && getline(cell_end + 1) !~ '^\s*%%'
        let cell_end += 1
    endwhile
    
    " Obtener el contenido de la celda
    let cell_content = getline(cell_start, cell_end)
    
    " Si la primera línea comienza con %%, eliminarla o limpiarla
    if len(cell_content) > 0 && cell_content[0] =~ '^\s*%%'
        " Conservar el resto de la línea después de %%
        let first_line = cell_content[0]
        let clean_first = substitute(first_line, '^\s*%%\s*', '', '')
        if clean_first != ''
            let cell_content[0] = clean_first
        else
            let cell_content = cell_content[1:]
        endif
    endif
    
    " Asegurarse que hay contenido para ejecutar
    if len(cell_content) == 0
        echo "Celda vacía, nada que ejecutar"
        return
    endif
    
    " Unir el contenido y enviarlo al controlador
    let joined_content = join(cell_content, "\n")
    
    py3 << EOF
try:
    if controller is not None:
        cell_content = vim.eval('joined_content')
        controller.run_cell(cell_content)
        print("Running cell...")
    else:
        print("Matlab controller not initialized. Run :MatlabLaunchServer first.")
except Exception as e:
    print(f"Error running Matlab cell: {e}")
EOF
endfunction

" Función para enviar Ctrl+C a Matlab (cancelar ejecución)
function! s:SendCtrlC()
    call s:InitController()
    py3 << EOF
try:
    if controller is not None:
        controller.send_ctrl_c()
        print("Sent interrupt signal to Matlab")
    else:
        print("Matlab controller not initialized")
except Exception as e:
    print(f"Error sending Ctrl+C to Matlab: {e}")
EOF
endfunction

" Create the commands
command! -nargs=1 MatlabRunCode call s:RunMatlabCode(<args>)
command! MatlabRunFile call s:RunCurrentFile()
command! -range MatlabRunSelection <line1>,<line2>call s:RunCurrentSelection()
command! MatlabRunCell call s:RunCurrentCell()
command! MatlabSendCtrlC call s:SendCtrlC()

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
        
        " NUEVO MAPEO: Ejecutar celda actual
        autocmd FileType matlab nnoremap <buffer><silent> <F8> :MatlabRunCell<CR>
        
        " NUEVO MAPEO: Cancelar ejecución en Matlab
        autocmd FileType matlab nnoremap <buffer><silent> <C-c> :MatlabSendCtrlC<CR>
    augroup END
endif

" Add a basic status line component
function! MatlabStatusLine()
    return 'Matlab'
endfunction

" Echo helpful info when the plugin loads
echo "Vim-Matlab plugin loaded. Use :MatlabLaunchServer to start the Matlab server."
echo "Use F5 to run file, F8 to run cell, F9 to run selection, Ctrl+C to cancel execution."
