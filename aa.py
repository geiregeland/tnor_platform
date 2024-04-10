from dash import dcc, Input,Output
from dash import html
import dash 
import subprocess
PROC_STAT_PATH='/proc/stat'
import plotly.graph_objs as go
    
    

# to app 
app = dash.Dash(__name__,assets_folder='/home/tnor/5GMediahub/Measurements/tnor_platform/assets')

app.layout = html.Div([
    dcc.Interval(id='interval1',interval=2000,n_intervals=0),
    html.H1(children="5GMediahub - TNOR testbed status",className="hello",style={'color':'#00361c','text-align':'center'}),
    #html.Div([
           html.Div(id='my-output',
                        style={
                        'backgroundColor':'darkslategray',
                        'color':'lightsteelblue',
                        'height':'550px',
                        'margin-left':'5px',
                        'width':'45%',
                        'text-align':'left' #,
                        #'display':'inline-block'
                        }),
            
    html.Div(id='my-output2',
               style={
                        'backgroundColor':'darkslategray',
                        'color':'lightsteelblue',
                        'height':'550px',
                        'margin-left':'5px',
                        'text-align':'left',
                        'width':'50%'#,
                        #'display':'inline-block'
               }),
    #]),
    html.Hr(className='gap'),
    #html.Div(id='my-output'),
    #html.Hr(className='gap'),
    dcc.Graph(id='graph')

 ])


@app.callback(
    Output('graph','figure'),
    [Input('interval1','n_intervals')])
def system_cpu(n):
    cpu_summary_str = open(PROC_STAT_PATH).read().split("\n")[0]
    parts = cpu_summary_str.split()
    assert parts[0] == "cpu"
    usage_data = parts[1:8]
    total_clock_ticks = sum(int(entry) for entry in usage_data)
    system_clicks=int(parts[3])
    user_clicks=int(parts[1])
    #print(system_clicks,user_clicks)
                    
    print([(system_clicks+n)/total_clock_ticks,user_clicks/total_clock_ticks])
    # 100 clock ticks per second, 10^9 ns per second
    fig=go.Figure(data=[go.Bar(x=[1,2],y=[100*(system_clicks)/total_clock_ticks,100*user_clicks/total_clock_ticks],marker_color='Gold')])
    return fig    


@app.callback(
    Output('my-output','children'),
    [Input('interval1','n_intervals')])
def display_output(n):
    # from this file, like this: 
    text_markdown = "\t"
    #cmd='ps -eo user,pid,%cpu,command --sort=%cpu|tail -10|sort -n -k3 -r >ps.txt'
    #cmd='top -b -n 1|head -30 | aha  --line-fix > assets/htop.html'
    cmd='top -b -n 1|head -25  > assets/htop.txt'
    
    #cmd='ps -eo user,pid,%cpu,command --sort=%cpu|tail -10|sort -n -k3 -r| aha --black --line-fix > assets/htop.html'
    #cmd='echo q|top | aha --black --line-fix > assets/htop.html'
    r=subprocess.run(cmd,capture_output=True,shell=True,text=True)

    #cmd2='microk8s.kubectl top pods --all-namespaces |aha --black --line-fix >assets/toppods.html'
    #r=subprocess.run(cmd2,capture_output=True,shell=True,text=True)
    #print(f"updating file {n}")
    f = open('assets/htop.txt').readlines()

        
    text=''
    i=0
    k=0
    for l in f:
        if i<6:
            if i!=5:
                text+='**'+l+'**'
            text+='  \n'
            i+=1
        else:
            tmp = l.split()
            tt=''
            kt='|'
            for j in tmp:
                if len(j):
                    tt+=j+'|'
                    if k==0:
                        kt+=':-----|'
            
            if k==0:
                text+='|'+tt+'    \n'
                text+=kt+'    \n'
                k=1
            else:
                text+='|'+tt+'    \n'
                
            #print(text)
    return dcc.Markdown(text)


    #return html.Iframe(id=f'label{n}',src=dash.get_asset_url("htop.html"),
      #              style={"height": "500px", "width": "40%"})

@app.callback(
    Output('my-output2','children'),
    [Input('interval1','n_intervals')])
def display_output2(n):
    # from this file, like this: 
    text_markdown = "\t"
    
    cmd2='microk8s.kubectl top pods --all-namespaces >assets/toppods.txt'
    r=subprocess.run(cmd2,capture_output=True,shell=True,text=True)
    #print(f"updating file {n}")
    f = open('assets/toppods.txt').readlines()

        
    text=''
    i=0
    k=0
    for l in f:
        tmp = l.split()
        tt=''
        kt='|'
        for j in tmp:
            if len(j):
                tt+=j+'|'
                if k==0:
                    kt+=':-----|'

        if k==0:
            text+='|'+tt+'    \n'
            text+=kt+'    \n'
            k=1
        else:
            text+='|'+tt+'    \n'

        #print(text)
    return dcc.Markdown(text)


    #return html.Iframe(id=f'label{n}',src=dash.get_asset_url("htop.html"),
      #              style={"height": "500px", "width": "40%"})




if __name__=='__main__':
    PORT = 8059
    SERVER='10.5.1.4'
    app.run_server(port=PORT,host=SERVER)
