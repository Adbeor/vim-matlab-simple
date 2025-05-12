" Simplified Vim-Matlab Plugin
" This plugin provides basic functionality to interact with Matlab from Vim

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
let s:server_script = expand('<sfile>:p:h') . '/matlab-server.py'
let s:controller_script = expand('<sfile>:p:h') . '/matlab_cli_controller.py'

" Define the split command based on user preference
if g:matlab_server_split ==? 'horizontal'
    let s:split_command = ':split term://'
else
    let s:split_command = ':vsplit term://'
endif

" Command to launch the Matlab server
command! MatlabLaunchServer :execute 'normal! ' . s:split_command . 'python ' . s:server_script . '<CR>'

" Create cell commands
command! MatlabNormalModeCreateCell :execute 'normal! :set paste<CR>m`O%%<ESC>``:set nopaste<CR>'
command! MatlabVisualModeCreateCell :execute 'normal! gvD:set paste<CR>O%%<CR>%%<ESC>P:set nopaste<CR>'
command! MatlabInsertModeCreateCell :execute 'normal! I%% '

" Default key mappings
if !exists('g:matlab_auto_mappings')
    let g:matlab_auto_mappings = 1
endif

" Function to run Matlab code via Python controller
function! s:RunMatlabCode(code)
    " This function will be implemented to use the Python controller
    " For now, we'll just echo the code
    echo "Would run Matlab code: " . a:code
endfunction

" Create the key mappings
if g:matlab_auto_mappings
    augroup matlab_mappings
        autocmd!
        autocmd FileType matlab nnoremap <buffer><silent> <C-l> :MatlabNormalModeCreateCell<CR>
        autocmd FileType matlab vnoremap <buffer><silent> <C-l> :<C-u>MatlabVisualModeCreateCell<CR>
        autocmd FileType matlab inoremap <buffer><silent> <C-l> <C-o>:MatlabInsertModeCreateCell<CR>
    augroup END
endif

" Add a basic status line component
function! MatlabStatusLine()
    return 'Matlab'
endfunction

" Echo helpful info when the plugin loads
echo "Vim-Matlab simplified plugin loaded. Use :MatlabLaunchServer to start the Matlab server."
