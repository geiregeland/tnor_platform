import dash
from dash import dcc
from dash import html
from dash.dependencies import Input, Output
import os
path1 = 'Logs/nbi_measure.log'

def intersperse(lst, item):
    result = [item] * (len(lst) * 2 - 1)
    result[0::2] = lst
    return result

app = dash.Dash(__name__)

app.layout = html.Div(style={'backgroundColor': 'white', 'color': 'black'}, children=[
                               dcc.Input(
                                    id = 'text-input',
                                    placeholder = '', style= dict(display = "none"),
                                    type = 'text',
                                    value = 1),
                            
                            html.Div(id = 'text-display'),

                  
                                dcc.Interval(id='interval-component',
                                             interval = 1000,
                                             n_intervals=0),
                                     ])

@app.callback(
    [Output(component_id='interval-component', component_property='interval')],
    [Input('interval-refresh', 'value')])
def update_refresh_rate(value):
    return [value * 1000] 


@app.callback(Output('text-display','children'),[Input('text-input','n_intervals')])
def update_text_output_2(input_value):
    text_markdown = "\t"
    this_file = open('Logs/nbi_measure.log','r')
    lines = this_file.readlines()
    print("callback")
    r =intersperse(lines,html.Br())
    this_file.close()
    return r

if __name__ == '__main__':
    PORT = 8050
    SERVER='10.5.1.4'
    app.run_server(port=PORT,host=SERVER)
    #app.run_server(debug=True)
