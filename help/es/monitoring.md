---
title: Monitorización y alertas
category: monitoring
order: 1
summary: Sondeo programado, utilización y errores de los puertos, CPU y temperatura, umbrales de eventos, gráficos.
keywords: sondeo intervalo utilización tráfico errores cpu memoria temperatura umbral evento gráfico estadísticas poe
---
# Sondeo periódico {#polling}

Abra **Configuración** (el engranaje al final del menú) y active **Consultar los switches por SNMP periódicamente**. SwitchMap consultará todos los switches con dirección IP al intervalo elegido.

| Intervalo | Cuándo conviene |
|---|---|
| 1–2 minutos | Red pequeña donde se necesitan gráficos detallados |
| 5 minutos | Casi para todos |
| 10–15 minutos | Cientos de switches o enlaces lentos |

Sin sondeo periódico, los datos solo se actualizan con el botón **Consultar por SNMP** de la página del switch.

**Nombres de puertos, descripciones y VLAN**: con qué frecuencia leer los datos que casi no cambian: nombres y descripciones de puertos, VLAN y vecinos LLDP (para la topología).

| Modo | Cuándo elegirlo |
|---|---|
| Cada sondeo | La red se está construyendo, ampliando o reparando: los cambios se ven de inmediato |
| Una vez por hora | La red es estable: casi la mitad de solicitudes a los switches y menos carga en su CPU |

El estado de los puertos, el tráfico, los errores y las direcciones MAC se leen en cada sondeo en ambos modos. **Consultar por SNMP** en la página del switch siempre lee todo: púlselo después de cambiar algo en un switch en lugar de esperar una hora.

# Qué se mide {#metrics}

- **Estado del puerto**: con o sin enlace. Un cambio genera el evento «puerto caído» o «puerto activo».
- **Utilización**: la tasa de tráfico como porcentaje de la velocidad del puerto. Se calcula con la diferencia de contadores entre sondeos, así que aparece a partir del segundo.
- **Errores**: cuántos errores de recepción y transmisión se acumularon desde el último sondeo.
- **CPU, memoria, temperatura**: si el switch los informa por SNMP (depende del fabricante).
- **PoE**: consumo por puerto, si el switch admite POWER-ETHERNET-MIB.

# Umbrales de alerta {#thresholds}

En **Configuración → Umbrales de alerta**:

| Umbral | Evento |
|---|---|
| Utilización del puerto, % | El tráfico supera este porcentaje de la velocidad del puerto |
| Errores del puerto entre sondeos | Los errores aumentan: a menudo un cable defectuoso |
| Carga de CPU, % | La CPU del switch está sobrecargada |
| Temperatura, °C | Sobrecalentamiento |

Se genera un evento al superar un umbral y otro cuando el valor vuelve a la normalidad. **0** desactiva un umbral. Si un switch deja de responder, el evento «switch inaccesible» explica si aún responde al ping (entonces el problema es la configuración SNMP) o no (entonces es la red o la alimentación). Si un switch que sin duda está desconectado «responde al ping», vea [Un switch desconectado responde al ping](/help/troubleshooting#fake-ping).

# Gráficos {#charts}

En la página del switch el botón **Estadísticas** abre los gráficos:

- la tasa de tráfico de cualquier puerto (entrante y saliente);
- la CPU, la memoria y la temperatura del switch.

Los periodos van de 1 hora a 1 año. Los periodos largos usan datos por hora, por lo que los gráficos se cargan rápido. Cuánto historial se guarda: vea [Datos y copias de seguridad](/help/backups#retention).

# Eventos {#events}

Todos los eventos aparecen bajo la campana de la barra superior y en la columna **Alertas** de la página de inicio. Para recibirlos por Telegram o correo, configure las [notificaciones](/help/notifications).
