El objetivo del proyecto es ofrecer información sobre las lineas de transporte ferroviario y metro
de españa, con información de:
* Lineas
* Estaciones/Paradas
* Horarios
* Horario estimado según movimiento de los trenes

Para ello necesitamos acceder a datos abiertos, vamos a empezar con los de renfe

https://data.renfe.com/dataset
https://gtfsrt.renfe.com/vehicle_positions.json

https://data.renfe.com/dataset/horarios-viaje-cercanias

En la wikipedia estan las lineas con los colores y los logos.

Vamos a empezar con una implementación para sevilla y despues para el resto.

El funcionamiento es el siguiente:
* Obtenemos información estática de renfe de lineas, paradas, horarios, etc..
* Registramos el movimiento de los trenes cada x tiempo, para poder hacer un cálculo de cuando llegará a la estación.