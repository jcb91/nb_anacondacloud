"%PREFIX%\Scripts\jupyter-nbextension.exe" enable nb_anacondacloud --py --sys-prefix && "%PREFIX%\Scripts\jupyter-serverextension.exe" enable --py nb_anacondacloud --sys-prefix && if errorlevel 1 exit 1
