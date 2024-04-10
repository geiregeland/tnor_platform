from dash import dcc, Input,Output
from dash import html
import dash 
import subprocess


# to app 
app = dash.Dash(__name__,assets_folder='/home/tnor/5GMediahub/Measurements/tnor_platform/assets')

app.layout = html.Div([
    dcc.Interval(id='interval1',interval=2000,n_intervals=0),

    html.Div(id='my-output')

    
    #html.Iframe(src=dash.get_asset_url("toppods.html"),
     #               style={"height": "367px", "width": "50%"})       

])


@app.callback(
    Output('my-output','children'),
    [Input('interval1','n_intervals')])
def display_output(n):
    # from this file, like this: 
    text_markdown = "\t"
    #cmd='ps -eo user,pid,%cpu,command --sort=%cpu|tail -10|sort -n -k3 -r >ps.txt'
    cmd='top -b -n 1|head -30 | aha  --line-fix > assets/htop.html'
    #cmd='ps -eo user,pid,%cpu,command --sort=%cpu|tail -10|sort -n -k3 -r| aha --black --line-fix > assets/htop.html'
    #cmd='echo q|top | aha --black --line-fix > assets/htop.html'
    r=subprocess.run(cmd,capture_output=True,shell=True,text=True)

    cmd2='microk8s.kubectl top pods --all-namespaces |aha --black --line-fix >assets/toppods.html'
    r=subprocess.run(cmd2,capture_output=True,shell=True,text=True)
    #print(f"updating file {n}")
    
    return html.Iframe(id=f'label{n}',src=dash.get_asset_url("htop.html"),
                    style={"height": "500px", "width": "50%"})




if __name__=='__main__':
    PORT = 8059
    SERVER='10.5.1.4'
    app.run_server(port=PORT,host=SERVER)
